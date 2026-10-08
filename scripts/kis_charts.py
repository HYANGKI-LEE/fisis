"""저축은행 Data Package(한국신용평가 양식) 항목 차트용 데이터/HTML 생성.

SBI 탭 기준으로 하늘색 구분자(재무상태표, 손익계산서, 차주별 원화대출금, 자산건전성, 수익성,
자본적정성, 유동성) 아래 항목들을 FISIS final_df에서 직접 계산해 "회사 x 항목 x 분기" JSON으로 내장하고,
브라우저(scripts/kis_charts.js)에서 회사/기간 선택에 맞춰 2열 차트로 그린다.

항목 정의는 Data Package 값과 SBI 2026.06 기준으로 맞춰봤고(이자이익, 수수료이익, 유가증권관련이익,
기타영업이익, 판관비, 대손상각비, 영업이익, 영업외이익, 당기순이익, 총여신, 고정이하여신, 연체액, BIS,
유동성비율 등 일치), 비율 항목은 주석(NIM/대손비용률/판관비율 정의)을 따랐다.
금액은 억원, 손익은 당분기, 비율은 분기 연율화(x4) 기준.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from dashboard.format import format_ym  # noqa: E402
from dashboard.loader import latest_final_df_path  # noqa: E402

START_YM = 200706   # final_df에 있는 가장 이른 분기부터
# 2015년 이전에는 반기(6/12월)만 공시되고 손익 '당분기' 값도 연/반기 누계와 섞여 있어서, 손익·연율화 비율은
# 분기 공시가 시작된 2016.Q1부터만 그린다 (잔액/FISIS 제공 비율 항목은 가능한 전 기간).
FLOW_START_YM = 201603
FLOW_PREFIXES = ("is_", "pf_")
ALL_LABEL = "저축은행 전체"

# 섹션 -> 서브탭 배치 (차주별 원화대출금은 자산건전성 탭 아래)
TAB_SECTIONS = {
    "대차대조표": ["bs"],
    "손익계산서": ["is"],
    "수익성": ["profit"],
    "자산건전성": ["asset", "borrower"],
    "자본적정성": ["capital"],
    "유동성": ["liquidity"],
}

SECTION_TITLES = {
    "bs": "재무상태표 (단위: 억원)",
    "is": "손익계산서 (단위: 억원, 당분기)",
    "profit": "수익성 (단위: %, 분기 연율화)",
    "asset": "자산건전성 (단위: 억원 / %)",
    "borrower": "차주별 원화대출금 (단위: 억원, 선: 대출금 합계 대비 비중 %)",
    "capital": "자본적정성",
    "liquidity": "유동성 (단위: %)",
}


def _mat(df: pd.DataFrame, qcols: list[str], table: str, code: str, item: str | None = None) -> pd.DataFrame:
    """통계표/코드 한 줄을 회사 x 분기 행렬(원 단위)로. 같은 코드에 구분명이 바뀐 행이 둘 이상이면
    분기별로 값이 있는 쪽을 합친다(groupby first)."""
    t = df[(df["통계표코드"].astype(str) == table) & (df["코드"] == code)]
    if item is not None:
        t = t[t["항목"] == item]
    t = t.copy()
    t[qcols] = t[qcols].apply(pd.to_numeric, errors="coerce")
    return t.groupby("금융회사명")[qcols].first()


def build_kis_payload(sector: str, rated: list[str]) -> dict | None:
    path = latest_final_df_path(sector)
    if path is None:
        return None
    df = pd.read_csv(path, index_col=0, encoding="cp949", low_memory=False)
    qcols = [c for c in df.columns if re.fullmatch(r"\d{6}", str(c)) and int(c) >= START_YM]
    if not qcols:
        return None

    # 분기 달력(빈 분기는 NaN) - 반기 공시 시절에도 직전 분기 shift가 어긋나지 않게 함
    cal, y, m = [], int(qcols[0]) // 100, int(qcols[0]) % 100
    while y * 100 + m <= int(qcols[-1]):
        cal.append(f"{y * 100 + m:06d}")
        m += 3
        if m > 12:
            y, m = y + 1, m - 12

    base = _mat(df, qcols, "SE003", "A", "금액").reindex(columns=cal)
    companies = base.index.tolist()

    def g(table, code, item=None, scale=1e8):
        return _mat(df, qcols, table, code, item).reindex(index=companies, columns=cal) / scale

    def prev(x):  # 직전 분기말 값 (분기 열이 빈틈없이 이어져 있으므로 한 칸 shift)
        return x.shift(1, axis=1)

    A = lambda c: g("SE003", c, "금액")           # 자산
    L = lambda c: g("SE004", c, "금액")           # 부채 및 자본
    P = lambda c: g("SE006", c, "당분기")         # 손익(당분기)
    fill0 = lambda x: x.fillna(0)

    asset, cash, sec, loan = A("A"), A("A1"), A("A2"), A("A3")
    liab, dep, borrow, equity = L("A1"), L("A11"), L("A12"), L("A2")

    metrics: dict[str, dict] = {}

    def add_sum(key, d):
        metrics[key] = {"kind": "sum", "df": d}

    def add_ratio(key, num, den, mult=100.0):
        metrics[key] = {"kind": "ratio", "num": num, "den": den, "mult": mult}

    # ---------------- 재무상태표
    add_sum("bs_asset", asset)
    add_sum("bs_cash", cash)
    add_sum("bs_sec", sec)
    add_sum("bs_loan", loan)
    add_sum("bs_allow", -A("A31"))
    add_sum("bs_other", asset - fill0(cash) - fill0(sec) - fill0(loan))
    add_sum("bs_liab", liab)
    add_sum("bs_dep", dep)
    add_sum("bs_borrow", borrow)
    add_sum("bs_oliab", liab - fill0(dep) - fill0(borrow))
    add_sum("bs_equity", equity)
    add_sum("bs_cap", L("A21"))
    add_sum("bs_capsur", L("A22"))
    add_sum("bs_re", L("A23"))
    add_sum("bs_adj", L("A24"))
    add_sum("bs_oci", L("A25"))

    # ---------------- 손익계산서 (당분기)
    interest = P("A1") - P("B1")
    fee = P("A2") - P("B2")
    secg = P("A3") - P("B5")
    other = P("A24") - P("B3")
    op = P("C")
    prov_exp = P("B3G0")
    sga = P("B4")
    add_sum("is_total", op)           # Data Package 표에서 총영업이익 = 영업이익과 같은 값
    add_sum("is_int", interest)
    add_sum("is_fee", fee)
    add_sum("is_sec", secg)
    add_sum("is_oth", other)
    add_sum("is_sga", sga)
    add_sum("is_ppop", op + prov_exp)
    add_sum("is_prov", prov_exp)
    add_sum("is_op", op)
    add_sum("is_nonop", P("L"))
    add_sum("is_ni", P("K"))

    # ---------------- 수익성 (분기 연율화, 분모는 분기 평잔)
    avg_asset = (asset + prev(asset)) / 2
    earn_assets = cash + sec + loan + A("A51") + A("A52")
    avg_earn = (earn_assets + prev(earn_assets)) / 2
    add_sum("pf_avg", avg_asset)
    add_ratio("pf_roa", P("K") * 4, avg_asset)
    add_ratio("pf_ppop", (op + prov_exp) * 4, avg_asset)
    add_ratio("pf_nim", interest * 4, avg_earn)
    prov_cost = prov_exp + fill0(P("B53")) - fill0(P("A24D0")) - fill0(P("A4"))
    add_ratio("pf_prov", prov_cost * 4, avg_asset)
    add_ratio("pf_sga", sga * 4, avg_asset)

    # ---------------- 자산건전성
    tot_loan = g("SE008", "A1")
    substd = g("SE008", "A3")
    allow = g("SE008", "A6")
    overdue = g("SE019", "C1")
    add_sum("aq_loan", tot_loan)
    add_sum("aq_sub", substd)
    add_sum("aq_allow", allow)
    add_sum("aq_over", overdue)
    add_ratio("aq_overr", overdue, g("SE019", "C2"))
    add_ratio("aq_subr", substd, tot_loan)
    add_ratio("aq_cov", allow, substd)

    # ---------------- 차주별 원화대출금 (+ 대출금 합계 대비 비중)
    loan_sum = g("SE020", "D")
    add_sum("bw_total", loan_sum)
    bw = {
        "bw_corp": g("SE020", "A"), "bw_sme": g("SE020", "A1"), "bw_indiv": g("SE020", "A11"),
        "bw_hh": g("SE020", "B"), "bw_pub": g("SE020", "C"),
        "bw_sec": g("SE021", "A"), "bw_re": g("SE021", "A2"), "bw_guar": g("SE021", "B"),
        "bw_cred": g("SE021", "C"), "bw_etc": g("SE021", "D"),
        "bw_cons": g("SE036", "A2"), "bw_realty": g("SE036", "A6"),
    }
    for k, d in bw.items():
        add_sum(k, d)
        add_ratio(k + "_sh", d, loan_sum)

    # ---------------- 자본적정성
    rwa = g("SE016", "F")
    bis_cap = g("SE016", "E")
    add_sum("cp_rwa", rwa)
    add_sum("cp_cap", bis_cap)
    add_ratio("cp_bis", bis_cap, rwa)
    add_ratio("cp_lev", asset, equity, mult=1.0)

    # ---------------- 유동성
    add_ratio("lq_ratio", g("SE011", "A1"), g("SE011", "A2"))

    # ---------------- 회사별 / 업권 전체 시계열
    series: dict[str, dict] = {c: {} for c in companies + [ALL_LABEL]}

    def to_list(row):
        return [None if (v is None or not np.isfinite(v)) else round(float(v), 3) for v in row]

    for key, m in metrics.items():
        if m["kind"] == "sum":
            per = m["df"].reindex(companies)
            agg = per.sum(min_count=1)
        else:
            num, den = m["num"].reindex(companies), m["den"].reindex(companies)
            ok = num.notna() & den.notna() & (den != 0)
            per = (num / den.where(den != 0)) * m["mult"]
            agg = num.where(ok).sum(min_count=1) / den.where(ok).sum(min_count=1) * m["mult"]
        is_flow = key.startswith(FLOW_PREFIXES)
        flow_ok = np.array([int(q) >= FLOW_START_YM for q in cal])
        if is_flow:
            per = per.loc[:, flow_ok]
            per = per.reindex(columns=cal)          # 마스크된 분기는 NaN
            agg = agg.where(pd.Series(flow_ok, index=agg.index))
        for c in companies:
            vals = to_list(per.loc[c].to_numpy())
            if any(v is not None for v in vals):
                series[c][key] = vals
        vals = to_list(agg.to_numpy())
        if any(v is not None for v in vals):
            series[ALL_LABEL][key] = vals

    asset_latest = base[cal[-1]].fillna(0)
    companies_sorted = sorted(companies, key=lambda c: -asset_latest.get(c, 0))
    return {
        "quarters": [format_ym(int(q)) for q in cal],
        "allLabel": ALL_LABEL,
        "companies": [ALL_LABEL] + companies_sorted,
        "rated": [ALL_LABEL] + [c for c in companies_sorted if c in rated],
        "series": {k: v for k, v in series.items() if v},
    }


# 섹션 정의: (키, 표시명, 단위, 차트종류, 비중키 또는 None)
SECTIONS = {
    "bs": [(None, [
        ("bs_asset", "자산총계", "억원", "bar", None),
        ("bs_cash", "현금및예치금", "억원", "bar", None),
        ("bs_sec", "유가증권", "억원", "bar", None),
        ("bs_loan", "대출채권", "억원", "bar", None),
        ("bs_allow", "(대손충당금)", "억원", "bar", None),
        ("bs_other", "기타자산", "억원", "bar", None),
        ("bs_liab", "부채총계", "억원", "bar", None),
        ("bs_dep", "예수부채", "억원", "bar", None),
        ("bs_borrow", "차입부채", "억원", "bar", None),
        ("bs_oliab", "기타부채", "억원", "bar", None),
        ("bs_equity", "자본총계", "억원", "bar", None),
        ("bs_cap", "자본금", "억원", "bar", None),
        ("bs_capsur", "자본잉여금", "억원", "bar", None),
        ("bs_re", "이익잉여금(결손금)", "억원", "bar", None),
        ("bs_adj", "자본조정", "억원", "bar", None),
        ("bs_oci", "기타포괄손익누계액", "억원", "bar", None),
    ])],
    "is": [(None, [
        ("is_total", "총영업이익", "억원", "bar", None),
        ("is_int", "이자이익", "억원", "bar", None),
        ("is_fee", "수수료이익", "억원", "bar", None),
        ("is_sec", "유가증권관련이익", "억원", "bar", None),
        ("is_oth", "기타영업이익", "억원", "bar", None),
        ("is_sga", "판매비와관리비", "억원", "bar", None),
        ("is_ppop", "충당금적립전영업이익(PPOP)", "억원", "bar", None),
        ("is_prov", "대손상각비", "억원", "bar", None),
        ("is_op", "영업이익", "억원", "bar", None),
        ("is_nonop", "영업외이익", "억원", "bar", None),
        ("is_ni", "당기순이익", "억원", "bar", None),
    ])],
    "profit": [(None, [
        ("pf_avg", "총자산 평잔", "억원", "bar", None),
        ("pf_roa", "총자산이익률(ROA)", "%", "line", None),
        ("pf_ppop", "PPOP/총자산평잔", "%", "line", None),
        ("pf_nim", "순이자마진(NIM)", "%", "line", None),
        ("pf_prov", "대손비용률", "%", "line", None),
        ("pf_sga", "판관비율", "%", "line", None),
    ])],
    "asset": [(None, [
        ("aq_loan", "총여신", "억원", "bar", None),
        ("aq_sub", "고정이하여신", "억원", "bar", None),
        ("aq_allow", "대손충당금", "억원", "bar", None),
        ("aq_over", "연체액", "억원", "bar", None),
        ("aq_overr", "연체율", "%", "line", None),
        ("aq_subr", "고정이하여신비율", "%", "line", None),
        ("aq_cov", "대손충당금/고정이하여신", "%", "line", None),
    ])],
    "borrower": [
        (None, [("bw_total", "대출금 합계", "억원", "bar", None)]),
        ("차주별 구성", [
            ("bw_corp", "기업자금대출", "억원", "bar", "bw_corp_sh"),
            ("bw_sme", "중소기업대출", "억원", "bar", "bw_sme_sh"),
            ("bw_indiv", "개인사업자", "억원", "bar", "bw_indiv_sh"),
            ("bw_hh", "가계자금대출", "억원", "bar", "bw_hh_sh"),
            ("bw_pub", "공공 및 기타", "억원", "bar", "bw_pub_sh"),
        ]),
        ("담보별 구성", [
            ("bw_sec", "담보", "억원", "bar", "bw_sec_sh"),
            ("bw_re", "부동산 담보", "억원", "bar", "bw_re_sh"),
            ("bw_guar", "보증", "억원", "bar", "bw_guar_sh"),
            ("bw_cred", "신용", "억원", "bar", "bw_cred_sh"),
            ("bw_etc", "기타", "억원", "bar", "bw_etc_sh"),
        ]),
        ("업종별 구성", [
            ("bw_cons", "건설업", "억원", "bar", "bw_cons_sh"),
            ("bw_realty", "부동산업", "억원", "bar", "bw_realty_sh"),
        ]),
    ],
    "capital": [(None, [
        ("cp_rwa", "위험가중자산", "억원", "bar", None),
        ("cp_cap", "BIS기준 자기자본", "억원", "bar", None),
        ("cp_bis", "BIS기준 자기자본비율", "%", "line", None),
        ("cp_lev", "레버리지배율", "배", "line", None),
    ])],
    "liquidity": [(None, [
        ("lq_ratio", "유동성비율", "%", "line", None),
    ])],
}

SECTION_NOTES = {
    "is": "Data Package 표에서 총영업이익은 영업이익과 같은 값이라 같은 값으로 그렸어요. 기타영업이익 = 기타수익 - 기타비용(대손상각비 포함), "
          "유가증권관련이익 = 유가증권관련수익 - 유가증권관련비용이에요.",
    "profit": "ROA·PPOP/총자산평잔·판관비율·대손비용률은 (당분기 금액 ×4) ÷ 총자산 분기 평잔((당분기말+직전 분기말)/2), "
              "NIM = (이자수익-이자비용) ×4 ÷ 이자수익자산(현금및예치금+유가증권+대출채권+미수금+미수수익) 분기 평잔, "
              "대손비용률 = (대손상각비+대출채권관련손실-대손충당금환입-대출채권관련수익) ×4 ÷ 총자산 평잔이에요.",
    "asset": "연체율 = 연체액/총여신, 고정이하여신비율 = 고정이하여신/총여신, 대손충당금/고정이하여신 = 대손충당금적립잔액/고정이하분류여신이에요.",
    "capital": "레버리지배율 = 자산총계 ÷ 자본총계, BIS기준 자기자본비율 = BIS기준 자기자본 ÷ 위험가중자산이에요.",
    "borrower": "선은 각 항목이 대출금 합계(용도별)에서 차지하는 비중이에요. 업종별 구성은 2018.Q4부터 공시돼요.",
}


def render_kis_controls() -> str:
    presets = ["1Y", "3Y", "5Y", "전체", "설정"]
    btns = "".join(
        f'<button data-preset="{p}" onclick="{"kisCustomToggle" if p == "설정" else "kisPreset"}'
        f'({"this" if p == "설정" else f"\'{p}\',this"})">{p}</button>'
        for p in presets
    )
    return (
        '<div class="kis-controls">'
        '<div class="control-row"><label>회사(검색 가능) '
        f'<input type="text" class="kis-company" value="{ALL_LABEL}" list="kisCompanyList" autocomplete="off" '
        'onfocus="kisCompanyFocus(this)" onblur="kisCompanyBlur(this)" oninput="kisCompanyInput(this)"></label></div>'
        f'<div class="period-bar"><span class="period-label">기간</span>{btns}</div>'
        '<div class="custom-range kis-custom">'
        '<input type="text" class="kis-start" placeholder="2020.Q1" style="width:90px;"> ~ '
        '<input type="text" class="kis-end" placeholder="2026.Q2" style="width:90px;"> '
        '<button onclick="kisCustomApply(this)">적용</button></div>'
        '</div>'
    )


def render_kis_block(tab_label: str) -> str:
    """서브탭 하단에 붙일 Data Package 항목 차트 영역(빈 차트 div만; 그리기는 JS)."""
    sections = TAB_SECTIONS.get(tab_label)
    if not sections:
        return ""
    parts = ['<hr style="border:none;border-top:1px solid var(--border);margin:28px 0 8px;">',
             '<p class="caption">아래는 저축은행 Data Package(한국신용평가 양식) 항목이에요. 회사와 기간은 모든 탭에 공통 적용돼요.</p>',
             render_kis_controls()]
    for sec in sections:
        parts.append(f'<h4>{SECTION_TITLES[sec]}</h4>')
        if sec in SECTION_NOTES:
            parts.append(f'<p class="caption">{SECTION_NOTES[sec]}</p>')
        for group_title, items in SECTIONS[sec]:
            if group_title:
                parts.append(f'<h5 style="margin:18px 0 4px;color:var(--muted);">{group_title}</h5>')
            cells = "".join(
                f'<div class="cell"><div class="kis-title">{name} <span>({unit})</span></div>'
                f'<div id="kis-{key}" class="plotly-chart kis-chart" data-key="{key}" data-type="{kind}" '
                f'data-name="{name}" data-unit="{unit}" data-share="{share or ""}"></div></div>'
                for key, name, unit, kind, share in items
            )
            parts.append(f'<div class="grid" style="grid-template-columns:1fr 1fr;">{cells}</div>')
    return "".join(parts)


def render_kis_data_script(payload: dict) -> str:
    return ('<datalist id="kisCompanyList"></datalist>'
            '<script type="application/json" id="kis-data">'
            f'{json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}</script>')
