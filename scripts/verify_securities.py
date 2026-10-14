"""sec_data.py(FISIS 계산값)를 엑셀 증권사비교(회사제시 자료 기반) 값과 대조한다.

사용: python scripts/verify_securities.py [엑셀경로] [기간 예: 202606]
회사 x 항목별로 억원 단위 오차 1 이내(비율은 0.15 이내)면 일치로 본다.
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import openpyxl

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sec_data import SecData  # noqa: E402

# 엑셀 행 번호('2026(06)' 시트 기준) -> (이름, 접근자)
BS = {
    5: "bs_cash", 6: "bs_dep", 7: "bs_sec", 8: "bs_sec_stock", 9: "bs_sec_gov", 10: "bs_sec_corp", 11: "bs_sec_cp",
    12: "bs_sec_fund", 13: "bs_sec_fx", 14: "bs_sec_assoc", 15: "bs_sec_dlsec", 16: "bs_sec_etc", 18: "bs_deriv_a",
    19: "bs_loan", 20: "bs_ln_call", 21: "bs_ln_margin", 22: "bs_ln_corp", 23: "bs_ln_jg", 24: "bs_ln_etc", 25: "bs_ln_allow",
    26: "bs_oth_a", 27: "bs_oth_recv", 28: "bs_oth_etc", 29: "bs_oth_allow", 30: "bs_asset",
    31: "bs_dep_l", 32: "bs_dep_inv", 33: "bs_borrow_real", 34: "bs_b_call", 35: "bs_b_loan", 36: "bs_b_bond", 37: "bs_b_sub",
    38: "bs_client", 39: "bs_cb_rp", 40: "bs_cb_sec", 41: "bs_cb_dls", 42: "bs_cb_note", 43: "bs_cb_ima",
    44: "bs_deriv_l", 45: "bs_oth_l", 46: "bs_oth_l_pay", 47: "bs_oth_l_etc", 48: "bs_liab", 49: "bs_equity", 50: "bs_capital", 51: "bs_total",
}
IS = {54: "rev", 55: "r_fee", 56: "r_sec", 57: "r_der", 58: "r_int", 59: "cost", 60: "c_fee", 61: "c_sec", 62: "c_der",
      63: "c_int", 64: "net", 65: "prov", 66: "sga", 67: "op", 68: "nonop_r", 69: "nonop_c", 70: "pretax", 71: "ni"}
RATIO = {87: "pf_roa", 88: "pf_roe", 89: "pf_sga", 91: "aq_total", 92: "aq_watch", 93: "aq_sub", 94: "aq_allow",
         95: "aq_nwatch", 96: "aq_nsub", 98: "cp_ncap", 100: "cp_risk", 102: "cp_req", 103: None, 104: "cp_ncr",
         106: "cp_lev", 108: "lq_assets", 109: "lq_liab", 110: "lq_gap", 111: "lq_ratio"}


def val(sd: SecData, key: str, ym: str):
    m = sd.metrics[key]
    if m["kind"] == "sum":
        return m["df"][ym]
    return m["num"][ym] / m["den"][ym].where(m["den"][ym] != 0) * m["mult"]


def main():
    xlsx = Path(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].endswith(".xlsx") else Path(r"C:\Users\infomax\Downloads\(Data Sheet) 증권업 재무자료_2026.2Q.xlsx")
    ym = sys.argv[2] if len(sys.argv) > 2 else "202606"
    sheet = f"{ym[:4]}({ym[4:]})"
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    ws = wb[sheet]
    cols = {ws.cell(4, c).value: c for c in range(6, ws.max_column + 1) if isinstance(ws.cell(4, c).value, str)}
    sd = SecData()
    bad_total = 0
    rows = []
    for r, key in {**BS, **{k: v for k, v in RATIO.items() if v}}.items():
        rows.append((r, key, "m"))
    for r, k in IS.items():
        rows.append((r, k, "y"))
    for r, key, kind in rows:
        label = ws.cell(r, 5).value
        diffs = []
        for co, c in cols.items():
            if co not in sd.names:
                continue
            ex = ws.cell(r, c).value
            if not isinstance(ex, (int, float)):
                continue
            if kind == "y":
                mine = sd.IS_y[key][ym].get(co)
            else:
                mine = val(sd, key, ym).get(co)
            tol = 1.0 if (kind == "y" or key.startswith(("bs", "aq_total", "aq_watch", "aq_sub", "aq_allow", "cp_n", "cp_r", "lq_a", "lq_l", "lq_g"))) else 0.15
            if key in ("pf_roa", "pf_roe", "pf_sga", "aq_nwatch", "aq_nsub", "cp_ncr", "cp_lev", "lq_ratio"):
                tol = 0.15 if key not in ("cp_ncr",) else 3.0
            if mine is None or not np.isfinite(mine) or abs(mine - ex) > tol:
                diffs.append((co, ex, None if mine is None or not np.isfinite(mine) else round(float(mine), 2)))
        n = len(cols) - 0
        status = "OK " if not diffs else f"BAD({len(diffs)})"
        bad_total += bool(diffs)
        print(f"{status:8s} r{r:<4d} {str(label)[:22]:24s} {key}")
        for d in diffs[:4]:
            print("          ", d)
    print("불일치 항목 수:", bad_total, "/", len(rows))


if __name__ == "__main__":
    main()
