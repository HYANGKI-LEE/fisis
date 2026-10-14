"""저축은행 '신용평가' 탭: 한국기업평가 상호저축은행업 신용평가방법론(2025.03.24, data/ 폴더 PDF)의 평가요소·등급 기준·가중치를
FISIS 데이터에 적용해 회사별 모델등급을 계산한다.

방법론 문서(3쪽 표, 8쪽 표 3)에서 확인한 것: 평가요소와 등급(AA/A/BBB/BB/B)별 기준값, 가중치(사업 50 : 재무 50),
지표 산출 기준(총자산시장점유율·레버리지배율·BIS비율은 최근 결산 기준, ROA·NIM·고정이하여신비율·대손충당금/고정이하여신은
최근 3개년 금액가중 평균, 유동성비율은 직전 4개 분기말 평균), NIM·레버리지배율·유동성비율 산식.
문서에 없는 것(= 이 모듈의 가정): 등급을 점수로 바꾸는 방법과 최종 모델등급 환산 구간, 정성항목(산업위험, 대출포트폴리오 위험,
경영 및 리스크 관리) 등급. 이들은 화면에서 선택/설명으로 드러낸다.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

import kis_charts  # noqa: E402
from dashboard.loader import latest_final_df_path  # noqa: E402

GRADES = ["AA", "A", "BBB", "BB", "B"]
RATED_CSV = REPO_DIR / "output" / "(E)상호저축은행" / "신용등급_전체80개사.csv"
ALL_LABEL = kis_charts.ALL_LABEL


def _num(x):
    return None if x is None or not np.isfinite(x) else round(float(x), 4)


def build_rating_payload(sector: str) -> dict | None:
    path = latest_final_df_path(sector)
    if path is None:
        return None
    df = pd.read_csv(path, index_col=0, encoding="cp949", low_memory=False)
    qcols_all = [c for c in df.columns if re.fullmatch(r"\d{6}", str(c))]
    q4 = [c for c in qcols_all if c.endswith("12") and int(c) >= 201603]
    if len(q4) < 4:
        return None
    fy_end = q4[-1]                                   # 최근 결산(12월) 기준
    fy = int(fy_end[:4])
    years = [fy - 2, fy - 1, fy]                       # 최근 3개년
    # 필요한 분기 열: (fy-3)년 12월 ~ fy년 12월
    need = [f"{y}{m:02d}" for y in range(fy - 3, fy + 1) for m in (3, 6, 9, 12) if f"{y}{m:02d}" in qcols_all]
    need = [c for c in need if int(c) >= (fy - 3) * 100 + 12]
    if len(need) < 13:
        return None

    def M(table, code, item=None):
        return kis_charts._mat(df, need, table, code, item)

    names = M("SE003", "A", "금액").index.tolist()

    def mx(table, code, item=None):
        return M(table, code, item).reindex(index=names, columns=need)

    asset = mx("SE003", "A", "금액")
    cash, sec, loan = mx("SE003", "A1", "금액"), mx("SE003", "A2", "금액"), mx("SE003", "A3", "금액")
    equity = mx("SE004", "A2", "금액")
    earn = cash + sec + loan                                      # 이자수익자산 = 예치금+유가증권+대출채권(순, 대손충당금 차감)

    def P(code):
        return mx("SE006", code, "당분기")

    z = lambda x: x.fillna(0)
    int_inc = z(P("A13")) + z(P("A16")) + z(P("A17")) + z(P("A18")) + z(P("A11"))   # 대출채권이자+유가증권이자+예치금이자
    int_exp = z(P("B11")) + z(P("B12")) + z(P("B13")) + z(P("B15"))                  # 예수금+표지어음예수금+차입금+사채이자
    ni = P("K")
    # 이자수익/비용 행이 아예 없는 회사는 NaN으로 (fillna(0) 때문에 0이 되는 것 방지)
    has_int = P("A13").notna().any(axis=1)

    npt = fy_end
    cols_of = {y: [c for c in need if c.startswith(str(y))] for y in range(fy - 3, fy + 1)}

    def fy_sum(frame, y):
        return frame[cols_of[y]].sum(axis=1, min_count=1)

    def fy_avg5(frame, y):
        prev_end = f"{y - 1}12"
        pts = [prev_end] + cols_of[y]
        return frame[[c for c in pts if c in frame.columns]].mean(axis=1)

    # ----- 3개년 금액가중 평균: 분자·분모를 3년 합산해서 나눈다
    roa_n = sum(fy_sum(ni, y) for y in years)
    roa_d = sum(fy_avg5(asset, y) for y in years)
    nim_n = sum(fy_sum(int_inc, y) - fy_sum(int_exp, y) for y in years)
    nim_d = sum(fy_avg5(earn, y) for y in years)
    sub, tot_loan, allow = mx("SE008", "A3"), mx("SE008", "A1"), mx("SE008", "A6")
    ye = [f"{y}12" for y in years]
    sub_n, sub_d = sub[ye].sum(axis=1, min_count=1), tot_loan[ye].sum(axis=1, min_count=1)
    cov_n = allow[ye].sum(axis=1, min_count=1)

    # ----- 최근 결산 기준
    cap, rwa = mx("SE016", "E"), mx("SE016", "F")
    bis = cap[npt] / rwa[npt] * 100
    lev = asset[npt] / equity[npt]
    share_tot = asset[npt].sum()
    share = asset[npt] / share_tot * 100
    la, lb = mx("SE011", "A1"), mx("SE011", "A2")
    liq_cols = cols_of[fy]
    liq_n, liq_d = la[liq_cols].mean(axis=1), lb[liq_cols].mean(axis=1)

    def per_company(c):
        return {
            "share": _num(share.get(c)),
            "roa": _num(roa_n[c] / roa_d[c] * 100) if np.isfinite(roa_n[c]) and roa_d[c] else None,
            "nim": _num(nim_n[c] / nim_d[c] * 100) if has_int[c] and nim_d[c] else None,
            "subr": _num(sub_n[c] / sub_d[c] * 100) if sub_d[c] else None,
            "cov": _num(cov_n[c] / sub_n[c] * 100) if sub_n[c] else None,
            "lev": _num(lev.get(c)),
            "bis": _num(bis.get(c)),
            "liq": _num(liq_n[c] / liq_d[c] * 100) if liq_d[c] else None,
        }

    companies = {c: per_company(c) for c in names}
    # 업권 전체(합산): 점유율은 해당 없음
    s = lambda f: f.sum()
    all_row = {
        "share": None,
        "roa": _num(s(roa_n.dropna()) / s(roa_d[roa_n.notna()]) * 100),
        "nim": _num(s(nim_n[has_int].dropna()) / s(nim_d[has_int & nim_n.notna()]) * 100),
        "subr": _num(s(sub_n.dropna()) / s(sub_d[sub_n.notna()]) * 100),
        "cov": _num(s(cov_n.dropna()) / s(sub_n[cov_n.notna()]) * 100),
        "lev": _num(asset[npt].sum() / equity[npt][asset[npt].notna()].sum()),
        "bis": _num(cap[npt].sum() / rwa[npt][cap[npt].notna()].sum() * 100),
        "liq": _num(s(liq_n.dropna()) / s(liq_d[liq_n.notna()]) * 100),
    }

    # 참고: 신평사 실제 등급(신용등급_전체80개사.csv)
    refs = {}
    if RATED_CSV.exists():
        r = pd.read_csv(RATED_CSV, encoding="cp949").fillna("")
        for _, row in r.iterrows():
            parts = []
            for label, g, o in (("한신평", "한국신용평가_등급", "한국신용평가_전망"), ("NICE", "NICE신용평가_등급", "NICE신용평가_전망"),
                                ("한기평", "한국기업평가_등급", "한국기업평가_전망")):
                if row.get(g):
                    parts.append(f"{label} {row[g]}" + (f"({row[o]})" if row.get(o) else ""))
            if parts:
                refs[row["금융회사명"]] = " · ".join(parts)

    return {
        "fy": f"{fy}.12",
        "years": [f"{y}" for y in years],
        "allLabel": ALL_LABEL,
        "companies": companies,
        "all": all_row,
        "refs": refs,
        "order": sorted(names, key=lambda c: -(asset[npt].get(c) if np.isfinite(asset[npt].get(c, np.nan)) else 0)),
    }


# ============================================================ HTML
MAPPING_ROWS = [
    # (그룹, 세부그룹 또는 None, 평가요소, [AA, A, BBB, BB, B], 가중치)
    ("사업항목", None, "산업위험", ["낮음", "다소 낮음", "다소 높음", "높음", "매우 높음"], "10.0%"),
    ("사업항목", "시장지배력", "총자산시장점유율", ["≥ 8%", "≥ 4%", "≥ 2%", "≥ 1%", "< 1%"], "15.0%"),
    ("사업항목", None, "대출포트폴리오 위험", ["낮음", "다소 낮음", "다소 높음", "높음", "매우 높음"], "12.5%"),
    ("사업항목", None, "경영 및 리스크 관리", ["매우 우수", "우수", "양호", "열위", "미흡"], "12.5%"),
    ("재무항목", "수익성", "총자산순이익률(ROA)", ["≥ 3%", "≥ 2%", "≥ 1%", "≥ 0%", "< 0%"], "7.5%"),
    ("재무항목", "수익성", "순이자마진(NIM)¹⁾", ["≥ 4%", "≥ 3%", "≥ 2%", "≥ 1%", "< 1%"], "5.0%"),
    ("재무항목", "자산건전성", "고정이하여신비율", ["≤ 2.5%", "≤ 4.5%", "≤ 6.5%", "≤ 8.5%", "> 8.5%"], "5.0%"),
    ("재무항목", "자산건전성", "대손충당금/고정이하여신", ["≥ 120%", "≥ 100%", "≥ 80%", "≥ 60%", "< 60%"], "7.5%"),
    ("재무항목", "자본적정성", "레버리지배율²⁾", ["≤ 5배", "≤ 7.5배", "≤ 10배", "≤ 12.5배", "> 12.5배"], "10.0%"),
    ("재무항목", "자본적정성", "BIS기준 자기자본비율", ["≥ 16.5%", "≥ 13.5%", "≥ 10.5%", "≥ 8%", "< 8%"], "7.5%"),
    ("재무항목", "자금조달 및 유동성", "유동성비율³⁾", ["≥ 150%", "≥ 130%", "≥ 115%", "≥ 100%", "< 100%"], "7.5%"),
]


def render_mapping_table() -> str:
    """방법론 3쪽 '평가요소와 신용등급간 Mapping' 표."""
    group_span = {"사업항목": sum(1 for r in MAPPING_ROWS if r[0] == "사업항목"), "재무항목": sum(1 for r in MAPPING_ROWS if r[0] == "재무항목")}
    sub_span = {}
    for r in MAPPING_ROWS:
        if r[1]:
            sub_span[r[1]] = sub_span.get(r[1], 0) + 1
    out = ['<table class="rating-table"><thead><tr><th colspan="3">주요 평가요소</th>'
           + "".join(f"<th>{g}</th>" for g in GRADES) + "<th>가중치</th></tr></thead><tbody>"]
    seen_group, seen_sub = set(), set()
    for grp, sub, name, cells, w in MAPPING_ROWS:
        tr = ["<tr>"]
        if grp not in seen_group:
            seen_group.add(grp)
            tr.append(f'<td class="grp" rowspan="{group_span[grp]}">{grp}</td>')
        if sub is None:
            tr.append(f'<td colspan="2" class="item">{name}</td>')
        else:
            if sub not in seen_sub:
                seen_sub.add(sub)
                tr.append(f'<td class="sub" rowspan="{sub_span[sub]}">{sub}</td>')
            tr.append(f'<td class="item">{name}</td>')
        tr.extend(f"<td>{c}</td>" for c in cells)
        tr.append(f'<td class="w">{w}</td></tr>')
        out.append("".join(tr))
    out.append("</tbody></table>")
    note = ('<p class="caption">출처: 한국기업평가 상호저축은행업 신용평가방법론(2025.03.24) 3쪽. '
            '주1) 순이자마진(NIM) = (이자수익-이자비용)/이자수익자산평잔, 이자수익 = 대출채권이자+유가증권이자+예치금이자, '
            '이자비용 = 예수금이자+표지어음예수금이자+차입금이자+사채이자, 이자수익자산 = 대출채권+유가증권+예치금-대손충당금. '
            '2) 레버리지배율 = 총자산/자기자본. 3) 유동성비율 = 직전 4개 분기말 유동성자산 잔액 평균/유동성부채 잔액 평균 '
            '(유동성자산·부채 = 3개월 이내 만기 도래 자산·부채).</p>')
    return "".join(out) + note


RATING_NOTE = (
    "지표는 방법론의 산출 기준에 맞췄어요: 총자산시장점유율·레버리지배율·BIS비율은 최근 결산(12월) 기준, ROA·NIM·고정이하여신비율·"
    "대손충당금/고정이하여신은 최근 3개년 금액가중 평균(3년 분자 합 ÷ 3년 분모 합), 유동성비율은 최근 결산연도 4개 분기말 평균이에요. "
    "산업위험·대출포트폴리오 위험·경영 및 리스크 관리는 정성평가라 FISIS로 수치화할 수 없어서 위 드롭다운으로 직접 고르게 했어요(기본 BBB). "
    "점수 산출은 Scoring 엑셀(Rating Numeric Matrix)과 같아요: 평가요소 등급마다 평균평점(AAA 1, AA 3, A 6, BBB 9, BB 12, B 15, CCC 18)과 "
    "부도율평점(AAA 0.03, AA 0.11, A 0.30, BBB 1.63, BB 8.13, B 23.73, CCC 65)을 부여하고 가중치(방법론 표)로 가중평균한 것이 Total score예요. "
    "자기등급은 평균평점을 정수 구간(1=AAA, 2=AA+, 3=AA, 4=AA-, 5=A+, 6=A, 7=A-, 8=BBB+, 9=BBB …)으로, 부도율평점을 등급별 평점 구간"
    "(해당 등급 평점 이상 ~ 다음 등급 평점 미만)으로 환산해요. 엑셀의 부도율평점 환산은 등급 표기 행이 노치(AA+, AA0…)로 연결돼 있어 값이 어긋나서, "
    "같은 시트의 등급 행(AAA, AA, A, BBB, BB, B, CCC)에 맞춰 적용했어요. 엑셀의 누적평점 행(1, 3, 6, 10, 15, 21, 28)은 계산식이 없어 쓰지 않았어요. "
    "모델등급은 평가 출발점일 뿐 실제 신용등급(평정위원회 결정)과 다를 수 있어요."
)


def render_rating_tab(payload: dict | None) -> str:
    if payload is None:
        return '<p class="caption">신용평가 계산에 필요한 데이터가 부족해요.</p>'
    data = (f'<script type="application/json" id="rating-data">'
            f'{json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}</script>')
    qsel = lambda k, label: (
        f'<label>{label} <select class="rating-q" data-k="{k}" onchange="ratingRender()" style="min-width:90px;">'
        + "".join(f'<option value="{i}"{" selected" if g == "BBB" else ""}>{g}</option>' for i, g in enumerate(GRADES))
        + "</select></label>")
    controls = kis_charts.render_kis_controls(show_period=False)
    qctl = ('<div class="control-row" style="margin-top:8px;">'
            + qsel("ind", "산업위험") + qsel("port", "대출포트폴리오 위험") + qsel("mgmt", "경영 및 리스크 관리")
            + '<span class="caption" style="align-self:center;">정성평가 항목은 직접 선택해요(기본 BBB)</span></div>')
    body = (
        '<h4>평가요소와 신용등급간 Mapping</h4>' + render_mapping_table() +
        '<h4 id="ratingTitle">신용평가방법론 적용 결과</h4>'
        '<div class="kis-table-wrap"><table class="rating-table" id="ratingResult"></table></div>'
        '<h4>모델등급 산출</h4>'
        '<div class="kis-table-wrap"><table class="rating-table" id="ratingScore"></table></div>'
        '<p class="caption" id="ratingRef"></p>'
        f'<p class="caption">{RATING_NOTE}</p>'
    )
    return controls + qctl + body + data
