"""FISIS 데이터 자동 업데이트 (매일 점검, 새 분기 나왔을 때만 증분 수집).

    python request.py --lrgDiv_ {코드} --startBaseMm_ {다음 분기} --endBaseMm_ {공시된 최신 분기}
    python process.py --lrgDiv_ {코드}
    (scheduler/incremental_merge.py로 final_df에 새 분기 컬럼 추가)

목표: 모든 업권의 output/({코드}){업권}/final_df/ 에 항상 "FISIS에 공시된 가장
최근 분기"({YYYYMM}) 파일이 생겨 있게 하는 것.

- 10개 업권을 스레드로 동시에 점검/수집한다 (업권별로 request.py가 자체 프로세스로
  돌고 API 호출 간격(sleep)이 대부분의 시간이라, 병렬로 돌리면 가장 오래 걸리는
  업권(증권사 약 3.5시간) 시간으로 전체가 끝남).
- 업권별로 "기존 최신 다음 분기"부터 하나씩 공시 여부를 가벼운 호출로 확인해서
  공시된 마지막 분기까지 알아낸 뒤, 그 범위를 request.py 한 번으로 받는다 (호출 수는
  기간 폭과 무관하므로 여러 분기가 밀려 있어도 1회 수집으로 따라잡음).
- 새 분기가 하나도 없으면 아무 것도 하지 않는다.
- 하나라도 갱신되면 cross_append.py로 보험사(H+I)/캐피탈사(K+N+T) 후처리.
- 업권별 진행 로그는 scheduler/logs/{업권}.log 에 실시간으로 남는다.

주의: merge.py는 안 쓴다. merge.py는 "로컬에 있는 long_df/wide_df 전체"를 다시
모아서 final_df를 새로 생성하는 구조인데, 이 저장소는 final_df만 git에 남기고
long_df/wide_df는 로컬 전용(sparse-checkout)이라 과거 long_df가 로컬에 없음 -
merge.py를 그대로 돌리면 "이번에 받은 새 분기만" 있는 걸로 final_df를 덮어써서
과거 이력이 통째로 날아간다 (실제로 한 번 사고 났었음). 대신
scheduler/incremental_merge.py로 새 분기 wide_df를 기존 final_df에 "추가"만 한다.

옵션: --dry-run (공시 여부만 확인하고 수집/병합은 하지 않음), --only 업권명 ...

git commit/push는 이 스크립트가 아니라 run_daily.py 쪽에서 처리한다.
"""
import argparse
import datetime
import os
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

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




MAX_CATCHUP_QUARTERS = 12
HEAVY_STEP_SLOTS = threading.Semaphore(3)  # process/병합은 메모리를 꽤 써서 동시 실행 수 제한
PRINT_LOCK = threading.Lock()
LOG_DIR = os.path.join(REPO_ROOT, "scheduler", "logs")


class SectorLogger:
    """업권별로 scheduler/logs/{업권}.log 에 실시간으로 기록하고, 표준출력에도
    [업권] 접두어를 붙여 내보낸다 (동시에 도는 업권들의 출력이 섞여도 구분 가능)."""

    def __init__(self, sector: str):
        self.sector = sector
        os.makedirs(LOG_DIR, exist_ok=True)
        self.path = os.path.join(LOG_DIR, f"{sector}.log")
        self._f = open(self.path, "a", encoding="utf-8")

    def log(self, msg: str, echo: bool = True) -> None:
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self._f.write(f"[{stamp}] {msg}\n")
        self._f.flush()
        if echo:
            with PRINT_LOCK:
                _safe_print(msg if msg.startswith(f"[{self.sector}]") else f"[{self.sector}] {msg}")
                sys.stdout.flush()

    def close(self) -> None:
        self._f.close()


def _safe_print(text: str, file=None) -> None:
    """콘솔 코드페이지(cp949)가 못 그리는 문자 때문에 로그 출력 자체가 죽는 걸 방지."""
    stream = file or sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    stream.write(text.encode(encoding, errors="replace").decode(encoding) + "\n")


def run_step(args: list[str], logger: SectorLogger) -> bool:
    """자식 프로세스를 돌리면서 출력을 업권 로그에 실시간으로 흘려보냄."""
    logger.log(">>> " + " ".join(os.path.basename(a) if a == sys.executable else a for a in args), echo=False)
    proc = subprocess.Popen(
        args, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    tail: list[str] = []
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            logger.log("  " + line, echo=False)
            tail.append(line)
            tail = tail[-15:]
    rc = proc.wait()
    if rc != 0:
        logger.log(f"단계 실패(rc={rc}): " + " | ".join(tail[-5:]))
    return rc == 0


def find_latest_available_quarter(lrgDiv: str, existing: int, logger: SectorLogger) -> int:
    """existing 다음 분기부터 하나씩 공시 여부를 확인해서, 연속으로 공시된 마지막 분기를
    반환 (하나도 없으면 existing 그대로)."""
    today_ym = datetime.date.today().year * 100 + datetime.date.today().month
    latest = existing
    q = next_quarter_label(existing)
    for _ in range(MAX_CATCHUP_QUARTERS):
        if q > today_ym:
            break
        logger.log(f"{q} 공시 여부 확인 중...")
        if not probe_quarter_available(lrgDiv, q):
            logger.log(f"{q} 아직 미공시")
            break
        logger.log(f"{q} 공시 확인됨")
        latest = q
        q = next_quarter_label(q)
    return latest


def check_and_update_sector(sector: str, folder: str, dry_run: bool = False) -> bool:
    logger = SectorLogger(sector)
    try:
        lrgDiv = sector_lrgdiv_code(folder)
        lrgDivNm = Div_dict[lrgDiv]["Name"]

        existing = existing_max_period(sector)
        if existing is None:
            logger.log("기존 final_df가 없음 - 건너뜀 (최초 적재는 수동으로)")
            return False
        logger.log(f"기존 최신 분기: {existing}")

        try:
            latest = find_latest_available_quarter(lrgDiv, existing, logger)
        except Exception as e:  # noqa: BLE001
            logger.log(f"공시 여부 확인 중 에러: {e} - 건너뜀")
            return False

        if latest == existing:
            logger.log("새로 공시된 분기 없음 - 건너뜀")
            return False

        start_q = next_quarter_label(existing)
        logger.log(f"신규 분기 {start_q}~{latest} 수집 대상")
        if dry_run:
            logger.log("(dry-run) 수집/병합 생략")
            return False

        # 과거 버킷(200703_201612, 201703_...)은 그대로 두고 {start}_{latest} 버킷만 추가.
        # API 호출 수는 기간 폭과 무관하므로 여러 분기를 한 번에 받아도 시간은 같다.
        ok = False
        for attempt in (1, 2):
            ok = run_step(
                [sys.executable, "request.py", "--lrgDiv_", lrgDiv,
                 "--startBaseMm_", str(start_q), "--endBaseMm_", str(latest)], logger,
            )
            if ok:
                break
            logger.log(f"request.py 실패 (시도 {attempt}/2)")
        if not ok:
            return False

        with HEAVY_STEP_SLOTS:
            if not run_step([sys.executable, "process.py", "--lrgDiv_", lrgDiv], logger):
                return False
            try:
                new_path = merge_into_final_df(sector, lrgDiv, lrgDivNm)
            except Exception as e:  # noqa: BLE001
                logger.log(f"final_df 병합 실패: {e}")
                return False
        if new_path:
            logger.log(f"final_df 갱신: {new_path}")

        new_existing = existing_max_period(sector)
        updated = new_existing is not None and new_existing != existing
        if updated:
            logger.log(f"[{sector}] 업데이트됨: {existing} -> {new_existing}")
            if new_existing < latest:
                logger.log(f"주의: 공시 확인된 최신은 {latest}인데 final_df는 {new_existing}까지만 반영됨")
        else:
            logger.log("수집했지만 결과적으로 변화 없음")
        return updated
    except Exception as e:  # noqa: BLE001
        logger.log(f"에러: {e}")
        return False
    finally:
        logger.close()


def main() -> bool:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="공시 여부만 확인")
    parser.add_argument("--only", nargs="*", help="지정한 업권만 (예: 상호저축은행 증권사)")
    args = parser.parse_args()

    today = datetime.date.today()
    print(f"=== FISIS 자동 업데이트 점검 ({today}){' [dry-run]' if args.dry_run else ''} ===", flush=True)

    targets = {s: f for s, f in SECTOR_FOLDERS.items() if not args.only or s in args.only}
    results: dict[str, bool] = {}
    with ThreadPoolExecutor(max_workers=len(targets)) as ex:
        futures = {ex.submit(check_and_update_sector, s, f, args.dry_run): s for s, f in targets.items()}
        for fut in as_completed(futures):
            sector = futures[fut]
            try:
                results[sector] = fut.result()
            except Exception as e:  # noqa: BLE001
                results[sector] = False
                print(f"[{sector}] 에러: {e}", file=sys.stderr)

    any_updated = any(results.values())
    if any_updated:
        print("=== 업권 데이터 갱신됨 - 보험사/캐피탈사 후처리(cross_append) 실행 ===", flush=True)
        logger = SectorLogger("cross_append")
        for cat in ("보험사", "캐피탈사"):
            run_step([sys.executable, "cross_append.py", "--Category_", cat], logger)
        logger.close()
    else:
        print("=== 새로 공시된 분기 없음 - 아무 작업도 하지 않음 ===", flush=True)

    return any_updated


if __name__ == "__main__":
    updated = main()
    sys.exit(0 if updated else 1)
