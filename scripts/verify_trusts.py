"""부동산신탁 페이지 숫자를 NICE NDB '산업(횡단면)' 시트(2026.2Q)와 대조한다 (엑셀은 저장소에 두지 않고 경로를 인자로 받음).

사용: python scripts/verify_trusts.py "C:/Users/.../부동산신탁 NDB(NICE DATA BOOK)[2026.2Q].xlsx"
FISIS로 계산한 값(trust_data.py)과 NICE 값이 허용 오차(기본 0.15) 안인지 항목·회사별로 출력한다.
"""
import sys
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
warnings.filterwarnings("ignore")

import openpyxl  # noqa: E402

from trust_data import TrustData  # noqa: E402

# NICE 행 이름 -> (trust_data 지표 키, 분기값 종류) ; 최신 분기(2026.06) 값 비교
ROWS = {
    "총자산": "bs_asset", "자기자본": "bs_equity", "총부채": "bs_liab", "차입부채": "bs_borrow", "현금및예치금": "bs_cashdep",
    "유가증권": "bs_sec", "신탁계정대(총)": "bs_tl", "대손충당금(신탁계정대)": "bs_tl_allow", "대손충당금(총자산)": "bs_allow_tot",
    "영업수익": "is_rev_raw_ytd", "이자수익": "is_r_int_ytd", "이자비용": "is_c_int_ytd", "판관비": "is_c_sga_ytd", "당기순이익": "is_ni_ytd",
    "총자산순이익률(ROA)(%)": "pf_roa", "자기자본순이익률(ROE)(%)": "pf_roe", "판관비용률(%)": "pf_sgaa",
    "요주의이하자산비중(%)": "aq_watchr", "고정이하자산비중(%)": "aq_subr", "(대손충당금+자기자본)/요주의이하자산(%)": "aq_cov",
    "자기자본 대비 순고정이하자산비율(%)": "aq_netsub", "부채비율(%)": "bs_dr", "차입금의존도(%)": "bs_borrowr", "순차입금의존도(%)": "bs_netborrowr",
    "영업용순자본비율(%)": "cp_ncr", "유동비율(%)": "lq_ratio", "토지신탁수익비중(%)": "pf_landsh",
}
NAME_FIX = {"케이비부동산신탁": "KB부동산신탁"}


def main(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["산업(횡단면)"]
    header = [c.value for c in ws[5]]
    cols = {NAME_FIX.get(v, v): i for i, v in enumerate(header) if isinstance(v, str) and v.endswith(("신탁", "신탁사")) and v not in ("합산",)}
    td = TrustData()
    last = td.cal[-1]

    def val(key):
        m = td.metrics[key]
        if m["kind"] in ("sum", "share"):
            return m["df"][last]
        return m["num"][last] / m["den"][last].where(m["den"][last] != 0) * m["mult"]

    bad = tot = 0
    for r in range(6, ws.max_row + 1):
        label = ws.cell(r, 3).value
        label = str(label).strip() if label else ""
        if label not in ROWS:
            continue
        mine = val(ROWS[label])
        for name, i in cols.items():
            nice = ws.cell(r, i + 1).value   # header 리스트가 0부터라 +1이 엑셀 열 번호
            if not isinstance(nice, (int, float)) or name not in mine.index or not np.isfinite(mine[name]):
                continue
            tot += 1
            tol = 0.15 if "%" in label else 0.6
            if abs(mine[name] - nice) > tol:
                bad += 1
                print(f"  차이: {label} / {name}: FISIS {mine[name]:.2f} vs NICE {nice:.2f}")
    print(f"비교 {tot}건 중 허용 오차 초과 {bad}건")


if __name__ == "__main__":
    main(sys.argv[1])
