"""업권종합 페이지용 데이터: 업권별 연체율 / 고정이하여신비율 / 요주의이하여신비율 시계열 (FISIS final_df).

업권마다 FISIS에 있는 통계표가 달라서 업권별로 (분자, 분모) 통계표 코드를 지정하고, 회사별 분자·분모를 분기마다 합산해서 비율을 만든다
(분자·분모가 둘 다 있는 회사만 합산). 없는 업권은 해당 지표에서 빠진다.
  - 연체율: 국내은행(원화대출금 연체율), 상호저축은행, 신용카드사(1개월 이상 연체채권), 캐피탈사, 생명보험·손해보험(대출채권 연체)
  - 고정이하여신비율: 국내은행, 상호저축은행, 신용카드사, 캐피탈사, 증권사, 자산운용사, 금융지주회사, 부동산신탁(고정이하자산비율)
  - 요주의이하여신비율: 국내은행, 증권사, 자산운용사, 금융지주회사, 부동산신탁
금액 정의는 업권마다 달라서(여신 vs 자산 기준) 같은 이름이어도 값의 의미가 조금 다르다.
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from dashboard.format import format_ym  # noqa: E402
from dashboard.loader import latest_final_df_path  # noqa: E402

START_YM = 200803
METRICS = [("od", "연체율"), ("sub", "고정이하여신비율"), ("watch", "요주의이하여신비율")]

# 표 하나에서 (분자, 분모) = [(통계표코드, 코드, 항목)] 의 합. 항목 None이면 항목 구분 없음.
T = lambda t, c, i=None: (t, c, i)

SPEC = {
    "국내은행": {
        "od": ([T("SA040", "A2")], [T("SA040", "A1")]),
        "sub": ([T("SA015", "B4")], [T("SA015", "A")]),
        "watch": ([T("SA015", "B4"), T("SA015", "B6")], [T("SA015", "A")]),
    },
    "신용카드사": {
        "od": ([T("SC117", "A5")], [T("SC117", "A")]),
        "sub": ([T("SC008", "A4")], [T("SC008", "A")]),
    },
    "캐피탈사": {
        "od": ([T("SK117", "A5"), T("SN117", "A5"), T("ST117", "A5")], [T("SK117", "A"), T("SN117", "A"), T("ST117", "A")]),
        "sub": ([T("SK008", "A4"), T("SN008", "A4"), T("ST008", "A4")], [T("SK008", "A"), T("SN008", "A"), T("ST008", "A")]),
    },
    "상호저축은행": {
        "od": ([T("SE019", "C1")], [T("SE019", "C2")]),
        "sub": ([T("SE008", "A3")], [T("SE008", "A1")]),
    },
    "증권사": {
        "sub": ([T("SF312", "V", "고정이하")], [T("SF312", "V", "분류대상금액")]),
        "watch": ([T("SF311", "V", "요주의"), T("SF311", "V", "고정"), T("SF311", "V", "회수의문"), T("SF311", "V", "추정손실")],
                  [T("SF311", "V", "합계")]),
    },
    "자산운용사": {
        "sub": ([T("SG034", "V", "고정이하")], [T("SG034", "V", "분류대상금액")]),
        "watch": ([T("SG033", "V", "요주의"), T("SG033", "V", "고정"), T("SG033", "V", "회수의문"), T("SG033", "V", "추정손실")],
                  [T("SG033", "V", "합계")]),
    },
    "금융지주회사": {
        "sub": ([T("SL009", "B")], [T("SL009", "A")]),
        "watch": ([T("SL009", "A2"), T("SL009", "A3"), T("SL009", "A4"), T("SL009", "A5")], [T("SL009", "A")]),
    },
    "부동산신탁": {
        "sub": ([T("SM013", "A")], [T("SM013", "B")]),
    },
    "생명보험": {"od": ([T("SH113", "A0", "연체금액")], [T("SH113", "A0", "금액")])},
    "손해보험": {"od": ([T("SI113", "A0", "연체금액")], [T("SI113", "A0", "금액")])},
}
ORDER = ["국내은행", "신용카드사", "캐피탈사", "생명보험", "손해보험", "증권사", "자산운용사", "상호저축은행", "부동산신탁", "금융지주회사"]


def _calendar(first, last):
    cal, y, m = [], int(first) // 100, int(first) % 100
    while y * 100 + m <= int(last):
        cal.append(f"{y * 100 + m:06d}")
        m += 3
        if m > 12:
            y, m = y + 1, m - 12
    return cal


def _sum_mat(df, qcols, specs):
    """specs 각 항목의 회사 x 분기 행렬을 더한다(회사별로 하나라도 값이 있으면 합산)."""
    total = None
    for table, code, item in specs:
        t = df[(df["통계표코드"].astype(str) == table) & (df["코드"] == code)]
        if item is not None and "항목" in t.columns:
            t = t[t["항목"] == item]
        m = t.groupby("금융회사코드")[qcols].first()
        total = m if total is None else total.add(m, fill_value=0).where(total.notna() | m.notna())
    return total


def build_overview_payload() -> dict:
    all_q = set()
    series: dict[str, dict] = {}
    for sector, spec in SPEC.items():
        path = latest_final_df_path(sector)
        if path is None:
            continue
        df = pd.read_csv(path, encoding="cp949", index_col=0, low_memory=False)
        qcols = [c for c in df.columns if re.fullmatch(r"\d{6}", str(c)) and int(c) >= START_YM]
        df[qcols] = df[qcols].apply(pd.to_numeric, errors="coerce")
        series[sector] = {}
        for key, (num_s, den_s) in spec.items():
            num, den = _sum_mat(df, qcols, num_s), _sum_mat(df, qcols, den_s)
            if num is None or den is None:
                continue
            num, den = num.reindex(den.index), den
            ok = num.notna() & den.notna() & (den > 0)
            ratio = num.where(ok).sum() / den.where(ok).sum() * 100
            ratio = ratio.where(ok.any())
            series[sector][key] = ratio
            all_q |= set(ratio.dropna().index)
        print(f"  {sector}: " + ", ".join(f"{k} {v.dropna().index[0] if v.notna().any() else '-'}~{v.dropna().iloc[-1]:.2f}" for k, v in series[sector].items() if v.notna().any()), flush=True)
    cal = _calendar(min(all_q), max(all_q))
    out = {}
    for sector in ORDER:
        if sector not in series:
            continue
        out[sector] = {}
        for key, ratio in series[sector].items():
            vals = ratio.reindex(cal)
            lst = [None if (v is None or not np.isfinite(v)) else round(float(v), 4) for v in vals]
            if any(v is not None for v in lst):
                out[sector][key] = lst
    return {"quarters": [format_ym(int(q)) for q in cal], "sectors": [s for s in ORDER if s in out], "series": out,
            "metrics": [{"k": k, "n": n} for k, n in METRICS]}


if __name__ == "__main__":
    p = build_overview_payload()
    print(len(p["quarters"]), p["quarters"][0], p["quarters"][-1], p["sectors"])
