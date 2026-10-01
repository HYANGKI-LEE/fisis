"""FISIS 데이터 자동 업데이트 (매일 점검, 새 분기 나왔을 때만 전체 재수집).

기존 수동 작업 방식 그대로:
    python request.py --lrgDiv_ {코드} --startBaseMm_ {기존 버킷 시작점} --endBaseMm_ {최신}
    python process.py --lrgDiv_ {코드}
    python merge.py --lrgDiv_ {코드}
를 config.py의 Div_dict를 참고해 업권별로 돌리되, 매일 무겁게 전체를 다시 받는 대신
"다음 분기 데이터가 FISIS에 실제로 올라왔는지"를 가벼운 API 호출 1~2번으로 먼저
확인하고, 올라온 업권에 대해서만 기존 방식(시작점 고정, 끝점만 확장)으로 전체를
재수집한다. 하나라도 갱신되면 cross_append.py로 보험사/캐피탈사 후처리까지 실행.

git commit/push는 이 스크립트가 아니라 예약 작업 프롬프트 쪽에서 처리한다.
"""
import datetime
import glob
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import fisis_getter  # noqa: E402
from config import Div_dict  # noqa: E402
from dashboard.loader import SECTOR_FOLDERS, latest_final_df_path  # noqa: E402

PERIOD_RE = re.compile(r"_(\d{6})\.csv$")
FOLDER_CODE_RE = re.compile(r"^\((\w)\)")
BUCKET_RE = re.compile(r"^(\d{6})_(\d{6})$")

DEFAULT_BUCKET_START = 201703


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
    """final_df 파일명(lrgDivNm_{최신분기}.csv)에서 이미 받아둔 최신 분기를 읽음."""
    path = latest_final_df_path(sector)
    if path is None:
        return None
    m = PERIOD_RE.search(os.path.basename(path))
    return int(m.group(1)) if m else None


def current_bucket_start(lrgDiv: str, lrgDivNm: str) -> int:
    """long_df 폴더명({시작}_{끝})을 보고 현재 쓰고 있는 버킷의 시작점을 찾음.
    여러 smlDiv 중 가장 최근(끝이 가장 큰) 버킷의 시작점을 기준으로 삼는다."""
    pattern = os.path.join(REPO_ROOT, "output", f"({lrgDiv}){lrgDivNm}", "*", "long_df", "*_*")
    candidates = []
    for d in glob.glob(pattern):
        m = BUCKET_RE.match(os.path.basename(d))
        if m:
            candidates.append((int(m.group(2)), int(m.group(1))))  # (end, start)
    if not candidates:
        return DEFAULT_BUCKET_START
    candidates.sort()
    return candidates[-1][1]


def probe_quarter_available(lrgDiv: str, quarter: int) -> bool:
    """회사 1개 + 통계표 1개로만 가볍게 조회해서 해당 분기 데이터가 FISIS에
    올라왔는지 확인. 업권 전체를 다시 받기 전에 먼저 이걸로 걸러낸다."""
    sml_div = Div_dict[lrgDiv]["SmlDiv"][0]

    companies = fisis_getter.getCompanySearch(partDiv=lrgDiv)
    company_list = [c for c in companies["result"]["list"] if "[폐]" not in c["finance_nm"]]
    if not company_list:
        return False
    finance_cd = company_list[0]["finance_cd"]

    stat_list_result = fisis_getter.getStatisticsListSearch(lrgDiv=lrgDiv, smlDiv=sml_div)
    stat_list = stat_list_result["result"]["list"]
    if not stat_list:
        return False
    list_no = stat_list[0]["list_no"]

    result = fisis_getter.getStatisticsInfoSearch(
        financeCd=finance_cd, listNo=list_no, term="Q",
        startBaseMm=str(quarter), endBaseMm=str(quarter),
    )
    if not result:
        return False
    res = result.get("result", {})
    return res.get("err_cd") == "000" and len(res.get("list", [])) > 0


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


def check_and_update_sector(sector: str, folder: str, today: datetime.date) -> bool:
    lrgDiv = sector_lrgdiv_code(folder)
    lrgDivNm = Div_dict[lrgDiv]["Name"]

    existing = existing_max_period(sector)
    if existing is None:
        print(f"[{sector}] 기존 final_df가 없음 - 건너뜀 (최초 적재는 수동으로)")
        return False

    next_q = next_quarter_label(existing)
    print(f"[{sector}] 기존 최신: {existing} / 다음 분기({next_q}) 공시 여부 확인 중...")

    try:
        available = probe_quarter_available(lrgDiv, next_q)
    except Exception as e:  # noqa: BLE001
        print(f"[{sector}] 공시 여부 확인 중 에러: {e} - 건너뜀")
        return False

    if not available:
        print(f"[{sector}] {next_q} 아직 미공시 - 건너뜀")
        return False

    bucket_start = current_bucket_start(lrgDiv, lrgDivNm)
    target_end = current_quarter_label(today)
    print(f"[{sector}] {next_q} 신규 공시 확인됨! {bucket_start} ~ {target_end} 전체 재수집 시작")

    ok = run_step(
        ["python", "request.py", "--lrgDiv_", lrgDiv,
         "--startBaseMm_", str(bucket_start), "--endBaseMm_", str(target_end)]
    )
    if not ok:
        print(f"[{sector}] request.py 실패")
        return False

    run_step(["python", "process.py", "--lrgDiv_", lrgDiv])
    run_step(["python", "merge.py", "--lrgDiv_", lrgDiv])

    new_existing = existing_max_period(sector)
    updated = new_existing is not None and new_existing != existing
    if updated:
        print(f"[{sector}] 업데이트됨: {existing} -> {new_existing}")
    else:
        print(f"[{sector}] 재수집했지만 결과적으로 변화 없음")
    return updated


def main() -> bool:
    today = datetime.date.today()
    print(f"=== FISIS 자동 업데이트 점검 ({today}) ===")

    any_updated = False
    for sector, folder in SECTOR_FOLDERS.items():
        try:
            if check_and_update_sector(sector, folder, today):
                any_updated = True
        except Exception as e:  # noqa: BLE001
            print(f"[{sector}] 에러: {e}", file=sys.stderr)

    if any_updated:
        print("=== 업권 데이터 갱신됨 - 보험사/캐피탈사 후처리(cross_append) 실행 ===")
        run_step(["python", "cross_append.py", "--Category_", "보험사"])
        run_step(["python", "cross_append.py", "--Category_", "캐피탈사"])
    else:
        print("=== 새로 공시된 분기 없음 - 아무 작업도 하지 않음 ===")

    return any_updated


if __name__ == "__main__":
    updated = main()
    sys.exit(0 if updated else 1)
