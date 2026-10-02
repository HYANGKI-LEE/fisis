"""FISIS 데이터 자동 업데이트 (매일 점검, 새 분기 나왔을 때만 증분 수집).

    python request.py --lrgDiv_ {코드} --startBaseMm_ {다음 분기} --endBaseMm_ {다음 분기}
    python process.py --lrgDiv_ {코드}
    python merge.py --lrgDiv_ {코드}

를 config.py의 Div_dict를 참고해 업권별로 돌리되, 매일 무겁게 전체를 다시 받는 대신
"다음 분기 데이터가 FISIS에 실제로 올라왔는지"를 가벼운 API 호출 1~2번으로 먼저
확인하고, 올라온 업권에 대해서만 그 분기 하나만 담은 작은 버킷(예: 202606_202606)을
새로 추가한다 (과거 버킷인 200703_201612, 201703_202603 등은 건드리지 않고 그대로
둠 - 2017년부터 매번 전체를 다시 받으면 업권당 수십 분~수 시간씩 걸림). 여러 분기가
밀려있어도 한 번에 다 받지 않고 분기 하나씩만 처리하며, 다음 실행 때 그 다음 분기를
또 감지해서 자연스럽게 따라잡는다.

주의: merge.py는 안 쓴다. merge.py는 "로컬에 있는 long_df/wide_df 전체"를 다시
모아서 final_df를 새로 생성하는 구조인데, 이 저장소는 final_df만 git에 남기고
long_df/wide_df는 로컬 전용(sparse-checkout)이라 과거 long_df가 로컬에 없음 -
merge.py를 그대로 돌리면 "이번에 받은 새 분기만" 있는 걸로 final_df를 덮어써서
과거 이력이 통째로 날아간다 (실제로 한 번 사고 났었음). 대신
scheduler/incremental_merge.py로 새 분기 wide_df를 기존 final_df에 "추가"만 한다.

하나라도 갱신되면 cross_append.py로 보험사/캐피탈사 후처리까지 실행.

git commit/push는 이 스크립트가 아니라 run_daily.py 쪽에서 처리한다.
"""
import datetime
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import fisis_getter  # noqa: E402
from config import Div_dict  # noqa: E402
from dashboard.loader import SECTOR_FOLDERS, latest_final_df_path  # noqa: E402
from scheduler.incremental_merge import merge_into_final_df  # noqa: E402

PERIOD_RE = re.compile(r"_(\d{6})\.csv$")
FOLDER_CODE_RE = re.compile(r"^\((\w)\)")


def sector_lrgdiv_code(folder_name: str) -> str:
    m = FOLDER_CODE_RE.match(folder_name)
    if not m:
        raise ValueError(f"업권 코드를 못 찾음: {folder_name}")
    return m.group(1)


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


PROBE_COMPANY_LIMIT = 10


def probe_quarter_available(lrgDiv: str, quarter: int) -> bool:
    """통계표 1개로 회사를 최대 PROBE_COMPANY_LIMIT개까지 가볍게 조회해서
    해당 분기 데이터가 FISIS에 올라왔는지 확인. 업권 전체를 다시 받기 전에
    먼저 이걸로 걸러낸다.

    회사 1개만 보면 안 되는 이유: 특정 회사가 그 통계표를 그 분기에 보고하지
    않았을 뿐인데 "업권 전체가 아직 미공시"로 잘못 판단할 수 있음 - 실제로
    증권사/신기술금융사에서 1~2번째 회사는 0건이었지만 3~5번째 회사는 있었음."""
    sml_div = Div_dict[lrgDiv]["SmlDiv"][0]

    companies = fisis_getter.getCompanySearch(partDiv=lrgDiv)
    company_list = [c for c in companies["result"]["list"] if "[폐]" not in c["finance_nm"]]
    if not company_list:
        return False

    stat_list_result = fisis_getter.getStatisticsListSearch(lrgDiv=lrgDiv, smlDiv=sml_div)
    stat_list = stat_list_result["result"]["list"]
    if not stat_list:
        return False
    # 생명보험/손해보험 등은 보고서 양식이 바뀐 시점(예: IFRS17 전환) 기준으로
    # "YY.MM월 이전" 구버전 통계표가 목록 맨 앞에 오는 경우가 있음 - 그런 표로
    # 최신 분기를 조회하면 당연히 비어있으니, 구버전이 아닌 표를 우선 사용
    current_era = [s for s in stat_list if "이전" not in s["list_nm"]]
    list_no = (current_era[0] if current_era else stat_list[0])["list_no"]

    for company in company_list[:PROBE_COMPANY_LIMIT]:
        result = fisis_getter.getStatisticsInfoSearch(
            financeCd=company["finance_cd"], listNo=list_no, term="Q",
            startBaseMm=str(quarter), endBaseMm=str(quarter),
        )
        if not result:
            continue
        res = result.get("result", {})
        if res.get("err_cd") == "000" and len(res.get("list", [])) > 0:
            return True
    return False


def _safe_print(text: str, file=None) -> None:
    """콘솔 코드페이지(cp949)가 못 그리는 문자(예: UTF-8 디코딩 중 생긴 치환문자)
    때문에 로그 출력 자체가 죽는 걸 방지."""
    stream = file or sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    stream.write(text.encode(encoding, errors="replace").decode(encoding) + "\n")


def run_step(args: list[str]) -> bool:
    print(">>>", " ".join(args), flush=True)
    result = subprocess.run(
        args, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    tail = result.stdout[-3000:]
    if tail:
        _safe_print(tail)
    if result.returncode != 0:
        _safe_print(result.stderr[-3000:], file=sys.stderr)
    return result.returncode == 0


def check_and_update_sector(sector: str, folder: str) -> bool:
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

    print(f"[{sector}] {next_q} 신규 공시 확인됨! {next_q} 단일 분기 버킷으로 수집 시작")

    # 과거 버킷(200703_201612, 201703_{기존 최신}...)은 그대로 두고, 분기 하나당
    # {next_q}_{next_q} 형태의 새 버킷만 추가한다. 여러 분기가 밀려있어도 한 번에
    # {next_q}~오늘 범위를 다 받지 않고 분기 하나씩만 처리 - 다음 실행 때 그 다음
    # 분기를 또 감지해서 자연스럽게 따라잡는다.
    ok = run_step(
        [sys.executable, "request.py", "--lrgDiv_", lrgDiv,
         "--startBaseMm_", str(next_q), "--endBaseMm_", str(next_q)]
    )
    if not ok:
        print(f"[{sector}] request.py 실패")
        return False

    run_step([sys.executable, "process.py", "--lrgDiv_", lrgDiv])

    try:
        new_path = merge_into_final_df(sector, lrgDiv, lrgDivNm)
    except Exception as e:  # noqa: BLE001
        print(f"[{sector}] final_df 병합 실패: {e}")
        return False
    if new_path:
        print(f"[{sector}] final_df 갱신: {new_path}")

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
            if check_and_update_sector(sector, folder):
                any_updated = True
        except Exception as e:  # noqa: BLE001
            print(f"[{sector}] 에러: {e}", file=sys.stderr)

    if any_updated:
        print("=== 업권 데이터 갱신됨 - 보험사/캐피탈사 후처리(cross_append) 실행 ===")
        run_step([sys.executable, "cross_append.py", "--Category_", "보험사"])
        run_step([sys.executable, "cross_append.py", "--Category_", "캐피탈사"])
    else:
        print("=== 새로 공시된 분기 없음 - 아무 작업도 하지 않음 ===")

    return any_updated


if __name__ == "__main__":
    updated = main()
    sys.exit(0 if updated else 1)
