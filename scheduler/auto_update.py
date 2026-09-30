"""FISIS 데이터 증분 자동 업데이트.

업권별로 이미 받아놓은 final_df의 최신 분기를 확인하고, 그 이후 ~ 오늘 기준
분기까지만 request.py -> process.py -> merge.py를 순서대로 돌려서
output/**/final_df를 최신 상태로 재생성한다.

이 스크립트는 데이터 수집/가공만 담당하고 git commit/push는 하지 않는다
(예약 작업 프롬프트에서 처리).
"""
import datetime
import glob
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from config import Div_dict  # noqa: E402
from dashboard.loader import SECTOR_FOLDERS, latest_final_df_path  # noqa: E402

PERIOD_RE = re.compile(r"_(\d{6})\.csv$")
FOLDER_CODE_RE = re.compile(r"^\((\w)\)")


def sector_lrgdiv_code(folder_name: str) -> str:
    m = FOLDER_CODE_RE.match(folder_name)
    if not m:
        raise ValueError(f"업권 코드를 못 찾음: {folder_name}")
    return m.group(1)


def current_quarter_label(today: datetime.date) -> int:
    """오늘이 속한 분기의 종료월 기준 라벨 (예: 2026-07-xx -> 202609)."""
    q = (today.month - 1) // 3 + 1
    return today.year * 100 + q * 3


def next_quarter_label(yyyymm: int) -> int:
    year, month = divmod(yyyymm, 100)
    month += 3
    if month > 12:
        year += 1
        month -= 12
    return year * 100 + month


def existing_max_period(sector: str) -> int | None:
    path = latest_final_df_path(sector)
    if path is None:
        return None
    m = PERIOD_RE.search(os.path.basename(path))
    return int(m.group(1)) if m else None


def clean_empty_period_files(lrgDiv: str, lrgDivNm: str, start: int, end: int) -> int:
    """빈(헤더만 있거나 0줄) 결과 파일을 지워서, 다음 실행 때 request.py가
    '이미 받은 파일'로 착각해 재시도를 건너뛰지 않게 한다."""
    period_dirs = glob.glob(
        os.path.join(REPO_ROOT, "output", f"({lrgDiv}){lrgDivNm}", "*", "long_df", f"{start}_{end}")
    )
    removed = 0
    for d in period_dirs:
        for f in glob.glob(os.path.join(d, "*.csv")):
            try:
                with open(f, "r", encoding="cp949", errors="ignore") as fh:
                    line_count = sum(1 for _ in fh)
                if line_count <= 1:
                    os.remove(f)
                    removed += 1
            except OSError:
                pass
    return removed


def run_step(args: list[str]) -> bool:
    print(">>>", " ".join(args), flush=True)
    result = subprocess.run(
        args, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    tail = result.stdout[-3000:]
    if tail:
        print(tail)
    if result.returncode != 0:
        print(result.stderr[-3000:], file=sys.stderr)
    return result.returncode == 0


def update_sector(sector: str, folder: str, today: datetime.date) -> bool:
    lrgDiv = sector_lrgdiv_code(folder)
    lrgDivNm = Div_dict[lrgDiv]["Name"]

    existing = existing_max_period(sector)
    target = current_quarter_label(today)

    if existing is not None and existing >= target:
        print(f"[{sector}] 이미 최신({existing}) - 건너뜀")
        return False

    start = next_quarter_label(existing) if existing else 199903
    end = target
    print(f"[{sector}] {start} ~ {end} 구간 수집 시도")

    ok = run_step(
        ["python", "request.py", "--lrgDiv_", lrgDiv, "--startBaseMm_", str(start), "--endBaseMm_", str(end)]
    )
    if not ok:
        print(f"[{sector}] request.py 실패")
        return False

    removed = clean_empty_period_files(lrgDiv, lrgDivNm, start, end)
    if removed:
        print(f"[{sector}] 빈 결과 {removed}개 삭제 (다음 실행 때 재시도됨)")

    run_step(["python", "process.py", "--lrgDiv_", lrgDiv])
    run_step(["python", "merge.py", "--lrgDiv_", lrgDiv])

    new_existing = existing_max_period(sector)
    updated = new_existing is not None and new_existing != existing
    print(f"[{sector}] {'업데이트됨: ' + str(existing) + ' -> ' + str(new_existing) if updated else '새 데이터 없음'}")
    return updated


def main() -> bool:
    today = datetime.date.today()
    print(f"=== FISIS 자동 업데이트 시작 ({today}) ===")

    any_updated = False
    for sector, folder in SECTOR_FOLDERS.items():
        try:
            if update_sector(sector, folder, today):
                any_updated = True
        except Exception as e:  # noqa: BLE001
            print(f"[{sector}] 에러: {e}", file=sys.stderr)

    print(f"=== 완료 - 새 데이터 발견: {any_updated} ===")
    return any_updated


if __name__ == "__main__":
    updated = main()
    sys.exit(0 if updated else 1)
