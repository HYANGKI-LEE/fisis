"""app.py(Streamlit)를 GitHub Pages용 정적 HTML(docs/index.html)로 내보낸다.

TradingCheckboard(../TradingCheckboard/scripts/generate_static_site.py)와 같은
방식: 업권별 "페이지"를 사이드바로 전환하고, Plotly 차트는 JSON으로 그대로
내장해서 브라우저에서 바로 렌더링한다(서버 없이 정적 파일만으로 동작).

상호저축은행은 FISIS 원본 사이트의 통계 분류 체계를 따라 하위탭 12개(주요지표 +
11개 준비중)로 먼저 구성한다 - 다른 업권은 아직 기존 단일 레이아웃 그대로.
주요지표 탭은 회사 비교 막대그래프(분기 드롭다운) + 당기순이익/ROA/ROE 추이
(검색 가능한 회사 드롭다운) + 표 순으로 배치하고, 전 회사 시계열 데이터를
JSON으로 통째로 내장해서 서버 없이 클라이언트에서 바로 전환되게 한다.
"""
import json
import sys
from pathlib import Path

import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from dashboard.loader import SECTOR_FOLDERS, latest_final_df_path, load_sector_long  # noqa: E402
from dashboard.kpis import build_kpi_table, build_credit_rating_table  # noqa: E402
import kis_charts  # noqa: E402
from dashboard.format import format_eok, format_pct, format_ym, latest_snapshot, latest_snapshot_full  # noqa: E402


# FISIS 원본 사이트의 저축은행 통계 분류 체계를 따름. "주요 지표"는 신평사 평가요소표
# 기준 요약(사업위험/재무위험), "최근 실적"은 기존 당기순이익/ROA/ROE 요약.
# 자산건전성 이후 10개는 아직 준비중 placeholder.
SAVINGS_BANK_TABS = [
    "주요 지표", "최근 실적", "수익성", "자산건전성", "여신건전성", "유동성",
    "자산 현황", "부채 현황", "부문별 손익 현황", "대출금 운용",
    "자본적정성", "대차대조표", "손익계산서",
]

# 차트 기본 스타일: 흰 배경, 가로(y축) 그리드만
_tpl = pio.templates["plotly_white"]
_tpl.layout.xaxis.showgrid = False
_tpl.layout.yaxis.showgrid = True
pio.templates.default = _tpl

_chart_counter = [0]


def chart_div(fig, div_id: str | None = None) -> str:
    """div_id를 직접 지정하면(JS에서 Plotly.react로 나중에 갱신할 차트) 그 id를 쓰고,
    아니면 자동 생성한다."""
    if div_id is None:
        _chart_counter[0] += 1
        div_id = f"chart{_chart_counter[0]}"
    payload = fig.to_json()
    return (f'<div id="{div_id}" class="plotly-chart"></div>'
            f'<script type="application/json" id="{div_id}-data">{payload}</script>'
            f'<script>renderChart("{div_id}");</script>')


def df_to_html(d: pd.DataFrame) -> str:
    cols = d.columns.tolist()
    html = ['<table class="data-table"><thead><tr>']
    for c in cols:
        html.append(f"<th>{c}</th>")
    html.append("</tr></thead><tbody>")
    for _, row in d.iterrows():
        html.append("<tr>")
        for c in cols:
            html.append(f"<td>{row[c]}</td>")
        html.append("</tr>")
    html.append("</tbody></table>")
    return "".join(html)


_tab_counter = [0]


def tabs_html(labels: list[str], bodies: list[str]) -> str:
    _tab_counter[0] += 1
    gid = f"tabgroup{_tab_counter[0]}"
    btns = "".join(
        f'<button class="tab-btn{" active" if i == 0 else ""}" '
        f'onclick="showTab(\'{gid}\',{i})">{lbl}</button>'
        for i, lbl in enumerate(labels)
    )
    panels = "".join(
        f'<div class="tab-panel{" active" if i == 0 else ""}" id="{gid}-{i}">{body}</div>'
        for i, body in enumerate(bodies)
    )
    return f'<div class="tabgroup" data-group="{gid}"><div class="tab-bar">{btns}</div>{panels}</div>'


# ================================================================ 기존 단일 레이아웃 (저축은행 외 9개 업권)
def render_sector(sector: str) -> str:
    long_df = load_sector_long(sector)
    kpi = build_kpi_table(long_df)
    if kpi.empty or kpi["당기순이익"].dropna().empty:
        return '<p class="caption">아직 수집된 데이터가 없어요.</p>'

    snap = latest_snapshot(kpi)
    display = snap.copy()
    display["기준분기"] = display["기준분기"].map(format_ym)
    display["당기순이익"] = display["당기순이익"].map(format_eok)
    display["전기대비증감률"] = display["전기대비증감률"].map(format_pct)
    display["ROA"] = display["ROA"].map(format_pct)
    display["ROE"] = display["ROE"].map(format_pct)
    table_html = df_to_html(display)

    top_company = snap["금융회사명"].iloc[0]
    trend = kpi[kpi["금융회사명"] == top_company].sort_values("년월").copy()
    trend["분기"] = trend["년월"].map(format_ym)

    fig1 = px.bar(trend, x="분기", y="당기순이익", title=f"{top_company} 당기순이익 추이")
    fig1.update_yaxes(title="당기순이익(원)")
    fig1.update_layout(height=380, margin=dict(t=50))

    roa_roe = trend.melt(
        id_vars="분기", value_vars=["ROA", "ROE"], var_name="지표", value_name="값"
    ).dropna(subset=["값"])
    chart2_html = '<p class="caption">ROA/ROE 데이터가 없어요.</p>'
    if not roa_roe.empty:
        fig2 = px.line(roa_roe, x="분기", y="값", color="지표", markers=True,
                        title=f"{top_company} ROA / ROE 추이")
        fig2.update_yaxes(title="%")
        fig2.update_layout(height=380, margin=dict(t=50))
        chart2_html = chart_div(fig2)

    note = '<p class="caption">회사별 최신 실적(당기순이익 1위 기준 추이 차트)만 보여줘요 - 이 업권은 아직 회사 선택 기능 적용 전이에요.</p>'

    return (
        f'<h4>회사별 최신 실적</h4>{table_html}'
        f'{note}'
        f'<div class="grid" style="grid-template-columns:1fr 1fr;">'
        f'<div class="cell">{chart_div(fig1)}</div>'
        f'<div class="cell">{chart2_html}</div>'
        f'</div>'
    )


# ================================================================ 저축은행: 탭 12개 레이아웃
TREND_METRICS = ("당기순이익", "ROA", "ROE")

# 회사명 x축 라벨은 업권 접미사를 떼서 짧게("오케이저축은행" -> "오케이")
SECTOR_NAME_SUFFIX = {"상호저축은행": "저축은행"}

TABLE_COLUMNS = [
    # (키, 표시 헤더, 포맷 함수, 정렬 기준이 되는 kpi 컬럼명)
    ("revenue", "영업수익", format_eok),
    ("opIncome", "영업이익", format_eok),
    ("opMargin", "영업이익률", format_pct),
    ("opYoy", "전년대비증감률", format_pct),
    ("netIncome", "당기순이익", format_eok),
    ("netMargin", "당기순이익률", format_pct),
    ("netYoy", "전년대비증감률", format_pct),
    ("roa", "ROA", format_pct),
    ("roe", "ROE", format_pct),
]
_SNAPSHOT_KEY_MAP = {
    "revenue": "영업수익", "opIncome": "영업이익", "opMargin": "영업이익률",
    "opYoy": "영업이익_전년대비증감률", "netIncome": "당기순이익", "netMargin": "당기순이익률",
    "netYoy": "당기순이익_전년대비증감률", "roa": "ROA", "roe": "ROE",
}


def build_sector_js_data(kpi: pd.DataFrame, companies: list[str], metrics=TREND_METRICS) -> dict:
    """회사 x 분기 전체 시계열을 JSON 구조로 변환 - 서버 없이 드롭다운으로
    회사/분기를 바꿔도 클라이언트에서 바로 차트를 다시 그릴 수 있게."""
    quarters = sorted(kpi["년월"].dropna().unique().tolist())
    quarter_labels = [format_ym(q) for q in quarters]

    series = {}
    for company in companies:
        g = (kpi[kpi["금융회사명"] == company]
             .drop_duplicates(subset="년월")
             .set_index("년월")
             .reindex(quarters))
        series[company] = {
            metric: [None if pd.isna(v) else float(v) for v in g[metric]]
            for metric in metrics
        }

    return {"quarters": quarter_labels, "companies": companies, "series": series}


def build_table_rows(snap_full: pd.DataFrame, columns=None, key_map=None) -> list[dict]:
    columns = columns or TABLE_COLUMNS
    key_map = key_map or _SNAPSHOT_KEY_MAP
    rows = []
    for _, r in snap_full.iterrows():
        row = {"company": r["금융회사명"]}
        for key, _, _ in columns:
            v = r[key_map[key]]
            row[key] = None if pd.isna(v) else float(v)
        rows.append(row)
    return rows


def render_main_tab_rich(sector_key: str, sector: str, kpi: pd.DataFrame, snap_full: pd.DataFrame) -> str:
    companies = snap_full["금융회사명"].tolist()  # 당기순이익 내림차순
    name_suffix = SECTOR_NAME_SUFFIX.get(sector, "")
    latest_q = format_ym(snap_full["기준분기"].max())

    js_data = build_sector_js_data(kpi, companies)
    js_data["nameSuffix"] = name_suffix
    js_data["tableRows"] = build_table_rows(snap_full)
    data_script = (f'<script type="application/json" id="data-{sector_key}">'
                    f'{json.dumps(js_data, ensure_ascii=False, separators=(",", ":"))}</script>')

    quarter_options = "".join(
        f'<option value="{q}"{" selected" if i == len(js_data["quarters"]) - 1 else ""}>{q}</option>'
        for i, q in enumerate(js_data["quarters"])
    )
    company_options = "".join(f"<option value=\"{c}\">" for c in companies)
    default_company = companies[0] if companies else ""

    year_options = ""
    if js_data["quarters"]:
        years = sorted({int(q.split(".")[0]) for q in js_data["quarters"]})
        default_year = 2018 if 2018 in years else years[0]
        year_options = "".join(
            f'<option value="{y}"{" selected" if y == default_year else ""}>{y}년~</option>'
            for y in years
        )
        year_options += f'<option value="0">전체</option>'

    bar_section = (
        '<h4>회사별 실적 비교</h4>'
        '<div class="control-row"><label>기준 분기 '
        f'<select id="quarterSelect-{sector_key}" onchange="onQuarterChange(\'{sector_key}\')">'
        f'{quarter_options}</select></label></div>'
        f'<div id="barChart-{sector_key}" class="plotly-chart"></div>'
    )

    trend_section = (
        '<h4>회사별 추이</h4>'
        '<div class="control-row">'
        '<label>회사 선택(검색 가능) '
        f'<input type="text" id="companySelect-{sector_key}" list="companyList-{sector_key}" '
        f'value="{default_company}" oninput="onCompanyChange(\'{sector_key}\')"></label>'
        f'<datalist id="companyList-{sector_key}">{company_options}</datalist>'
        '<label>조회 시작 '
        f'<select id="rangeSelect-{sector_key}" onchange="onCompanyChange(\'{sector_key}\')">'
        f'{year_options}</select></label>'
        '</div>'
        f'<div class="grid" style="grid-template-columns:1fr 1fr;">'
        f'<div class="cell"><div id="trendNI-{sector_key}" class="plotly-chart"></div></div>'
        f'<div class="cell"><div id="trendRoaRoe-{sector_key}" class="plotly-chart"></div></div>'
        f'</div>'
    )

    table_head = "".join(
        f'<th class="sortable" onclick="sortTable(\'{sector_key}\',\'{key}\')">{label} <span class="sort-arrow" '
        f'id="arrow-{sector_key}-{key}"></span></th>'
        for key, label, _ in TABLE_COLUMNS
    )
    table_section = (
        f'<h4>회사별 최신 실적 <span class="caption" style="font-weight:normal;">({latest_q} 기준)</span></h4>'
        f'<div style="overflow-x:auto;"><table class="data-table" id="table-{sector_key}">'
        f'<thead><tr><th class="sortable" onclick="sortTable(\'{sector_key}\',\'company\')">No</th>'
        f'<th class="sortable" onclick="sortTable(\'{sector_key}\',\'company\')">금융회사명 '
        f'<span class="sort-arrow" id="arrow-{sector_key}-company"></span></th>'
        f'{table_head}</tr></thead>'
        f'<tbody id="tbody-{sector_key}"></tbody></table></div>'
    )

    return (
        data_script + bar_section + trend_section + table_section +
        f'<script>initSectorMain("{sector_key}");</script>'
    )


# ================================================================ 주요 지표(신평사 평가요소표 기준)
CR_METRICS = [
    "총자산시장점유율", "충당금적립전영업이익률", "ROA", "연체율",
    "고정이하여신비율", "고정이하여신Coverage", "BIS자기자본비율", "유동성비율",
]
CR_NOTE = (
    '<p class="caption">신평사 저축은행 평가요소표(사업위험/재무위험) 기준 핵심 지표예요. '
    '정성평가 항목(경영관리능력, 대출포트폴리오 구성, 자본관리능력, 재무적 융통성)은 수치화가 안 돼서 제외했어요. '
    'FISIS가 연 1회(4분기)만 공시하는 ROA·충당금적립전영업이익률은 분기 금액으로 직접 계산(연율화)했어요.</p>'
)

# 회사별 지표 비교 드롭다운에만 추가되는 지표(추이 차트는 만들지 않음)
CR_BAR_ONLY_METRICS = ["대출이자수익률", "충당금적립전영업이익률(4분기누적)", "ROA(4분기누적)"]
CR_BAR_NOTE = ("대출이자수익률 = 연환산(×4) 당분기 대출금 이자수익 ÷ 대출채권 분기 평잔"
               "((당분기말 + 직전 분기말) / 2). "
               "ROA·충당금적립전영업이익률은 분기마다 연율화(당분기 금액 ×4 ÷ 총자산 분기 평잔)해서 계산하고, "
               "(4분기누적) 지표는 최근 4개 분기 합계 ÷ 총자산 평잔(기초~당분기말 5개 분기말 평균)이에요.")

RANGE_PRESETS = ["1Y", "3Y", "5Y", "10Y", "전체", "설정"]

RATED_CSV = REPO_DIR / "output" / "(E)상호저축은행" / "신용등급_전체80개사.csv"


def load_rated_companies(company_order: list[str]) -> list[str]:
    """신평사 유효등급 보유 회사(신용등급_전체80개사.csv의 '신평사유효등급보유'=O). company_order 순서 유지.
    파일이 없으면 빈 리스트 -> 화면에서는 전체 회사로 대체."""
    if not RATED_CSV.exists():
        return []
    r = pd.read_csv(RATED_CSV, encoding="cp949").fillna("")
    rated = set(r.loc[r["신평사유효등급보유"] == "O", "금융회사명"])
    return [c for c in company_order if c in rated]


# ================================================================ 대출금리 vs 경상이익률·대손비용률 산점도 (NICE 유효등급 보유사)
SCATTER_FOOTNOTE = (
    "경상이익률 = 이자이익률 - 판매관리비율 - 순수수료비용률 - 예금보험료율 (각 항목 = 연환산 기준 금액 ÷ 총자산 평잔). "
    "이자이익률 = (이자수익 - 이자비용) ÷ 총자산 평잔, 판매관리비율 = 판매비와관리비 ÷ 총자산 평잔, "
    "순수수료비용률 = (수수료비용 - 수수료수익) ÷ 총자산 평잔, 예금보험료율 = 예금보험료 ÷ 총자산 평잔. "
    "대손비용률 = (대손상각비 + 대출채권관련손실 - 대출채권관련수익) ÷ 총자산 평잔. "
    "연환산은 해당 연도 누계(1분기~기준 분기)를 4/분기수로 환산, 총자산 평잔은 전년말~기준 분기말 분기말 자산총계의 평균. "
    "대출금리 수준은 대출이자수익률(연환산 당분기 대출금이자수익 ÷ 대출채권 분기 평잔). "
    "대손 차감 후 경상이익률 = 경상이익률 - 대손비용률. 신평사(한신평·NICE·한기평) 유효등급 보유 회사만 표시. 자료: FISIS."
)


def build_scatter_points(sector: str) -> tuple[pd.DataFrame, str]:
    """신평사 유효등급 보유사별 (대출금리, 경상이익률, 대손비용률) - 최신 분기 기준. (df, 기준분기 라벨) 반환."""
    is_d = build_statement_data(sector, "is")
    bs_d = build_statement_data(sector, "bs")
    if is_d is None or bs_d is None or not RATED_CSV.exists():
        return pd.DataFrame(), ""
    r = pd.read_csv(RATED_CSV, encoding="cp949").fillna("")
    names = r.loc[r["신평사유효등급보유"] == "O", "금융회사명"].tolist()

    qlabels = is_d["quarters"]
    iq = len(qlabels) - 1
    n = int(qlabels[iq].split("Q")[1])   # 해당 연도 누계에 포함되는 분기 수
    if iq - n < 0 or iq < 1:
        return pd.DataFrame(), ""
    factor = 4 / n

    def ser(d, co, code):
        return d["series"].get(co, {}).get(code) or [None] * len(d["quarters"])

    def cum(co, code):
        s = ser(is_d, co, code)
        return sum((s[i] or 0) for i in range(iq - n + 1, iq + 1))

    rows = []
    for co in names:
        assets = ser(bs_d, co, "a_A")
        pts = [assets[i] for i in range(iq - n, iq + 1)]
        loans = ser(bs_d, co, "a_A3")
        a13 = ser(is_d, co, "A13")
        if any(v is None for v in pts) or loans[iq] is None or loans[iq - 1] is None or a13[iq] is None:
            continue
        avg = float(np.mean(pts))
        interest = (cum(co, "A1") - cum(co, "B1")) * factor / avg * 100
        sga = cum(co, "B4") * factor / avg * 100
        fee = (cum(co, "B2") - cum(co, "A2")) * factor / avg * 100
        deposit_ins = cum(co, "B35") * factor / avg * 100
        provision = (cum(co, "B3G0") + cum(co, "B53") - cum(co, "A4")) * factor / avg * 100
        rows.append({
            "회사": co,
            "대출금리": a13[iq] * 4 / ((loans[iq] + loans[iq - 1]) / 2) * 100,
            "경상이익률": interest - sga - fee - deposit_ins,
            "대손비용률": provision,
        })
    return pd.DataFrame(rows), qlabels[iq]


def render_scatter_section(sector: str) -> str:
    df, qlabel = build_scatter_points(sector)
    if df.empty:
        return ""
    suffix = SECTOR_NAME_SUFFIX.get(sector, "")
    short = lambda c: c.replace(suffix, "") if suffix else c
    x = df["대출금리"].to_numpy()
    xs = np.array([x.min(), x.max()])
    fits = {}
    for col in ("경상이익률", "대손비용률"):
        slope, icpt = np.polyfit(x, df[col].to_numpy(), 1)
        r2 = float(np.corrcoef(x, df[col])[0, 1] ** 2)
        fits[col] = (slope, icpt, r2)

    navy, blue = "#1F3864", "#2E75B6"
    year, q = qlabel.split(".Q")
    x_label = f"{year}.{q}Q"
    ya = fits["경상이익률"][0] * xs + fits["경상이익률"][1]
    yb = fits["대손비용률"][0] * xs + fits["대손비용률"][1]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[xs[0], xs[1], xs[1], xs[0]], y=[ya[0], ya[1], yb[1], yb[0]], fill="toself", mode="lines",
        fillcolor="rgba(255,224,130,0.45)", line=dict(width=0), hoverinfo="skip", showlegend=False))
    for col, color, symbol in (("경상이익률", navy, "square"), ("대손비용률", blue, "diamond")):
        fig.add_trace(go.Scatter(
            x=df["대출금리"], y=df[col], mode="markers", name=col,
            marker=dict(color=color, symbol=symbol, size=9),
            customdata=[short(c) for c in df["회사"]],
            hovertemplate="%{customdata}<br>대출금리 %{x:.2f}% / " + col + " %{y:.2f}%<extra></extra>"))
        slope, icpt, _ = fits[col]
        fig.add_trace(go.Scatter(
            x=xs, y=slope * xs + icpt, mode="lines", line=dict(color=color, dash="dot", width=3),
            hoverinfo="skip", showlegend=False))
    for i, (col, color) in enumerate((("경상이익률", navy), ("대손비용률", blue))):
        fig.add_annotation(xref="paper", yref="paper", x=0.06, y=0.97 - i * 0.07, showarrow=False,
                           text=f"<b>R² = {fits[col][2]:.4f}</b>", font=dict(color=color, size=14), xanchor="left")
    fig.update_layout(
        height=480, margin=dict(t=30, b=60), plot_bgcolor="white",
        xaxis=dict(title=f"회사별 대출금리 수준({x_label}, %)", showgrid=False, linecolor="#999"),
        yaxis=dict(title="총자산 대비(%)", showgrid=True, gridcolor="#e5e7eb", zeroline=True, zerolinecolor="#999", linecolor="#999"),
        legend=dict(x=0.8, y=0.12, bgcolor="rgba(255,255,255,0.7)"))
    # 2열: 오른쪽은 대손 차감 후 경상이익률(= 경상이익률 - 대손비용률)
    net = df["경상이익률"] - df["대손비용률"]
    slope, icpt = np.polyfit(x, net.to_numpy(), 1)
    r2_net = float(np.corrcoef(x, net)[0, 1] ** 2)
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df["대출금리"], y=net, mode="markers", name="대손 차감 후 경상이익률",
        marker=dict(color="#C0504D", symbol="circle", size=9),
        customdata=[short(c) for c in df["회사"]],
        hovertemplate="%{customdata}<br>대출금리 %{x:.2f}% / 대손 차감 후 경상이익률 %{y:.2f}%<extra></extra>"))
    fig2.add_trace(go.Scatter(
        x=xs, y=slope * xs + icpt, mode="lines", line=dict(color="#C0504D", dash="dot", width=3),
        hoverinfo="skip", showlegend=False))
    fig2.add_annotation(xref="paper", yref="paper", x=0.06, y=0.97, showarrow=False,
                        text=f"<b>R² = {r2_net:.4f}</b>", font=dict(color="#C0504D", size=14), xanchor="left")
    fig2.update_layout(
        height=480, margin=dict(t=30, b=60), plot_bgcolor="white",
        xaxis=dict(title=f"회사별 대출금리 수준({x_label}, %)", showgrid=False, linecolor="#999"),
        yaxis=dict(title="총자산 대비(%)", showgrid=True, gridcolor="#e5e7eb", zeroline=True, zerolinecolor="#999", linecolor="#999"),
        legend=dict(x=0.5, y=0.12, bgcolor="rgba(255,255,255,0.7)"))
    return (
        f'<h4>회사별 대출금리 수준과 경상이익률·대손비용률 <span class="caption" style="font-weight:normal;">'
        f'(단위: %, {qlabel} 기준 연환산, 신평사 유효등급 {len(df)}개사)</span></h4>'
        f'<div class="grid" style="grid-template-columns:1fr 1fr;">'
        f'<div class="cell">{chart_div(fig)}</div>'
        f'<div class="cell">{chart_div(fig2)}</div>'
        f'</div>'
        f'<p class="caption">{SCATTER_FOOTNOTE}</p>'
    )


def render_credit_rating_tab(sector_key: str, sector: str, kpi: pd.DataFrame, company_order: list[str]) -> str:
    long_df = load_sector_long(sector)
    cr = build_credit_rating_table(long_df)
    cr_full = cr  # ROA도 build_credit_rating_table에서 분기 연율화로 계산

    if cr_full.empty:
        return '<p class="caption">아직 수집된 데이터가 없어요.</p>'

    js_data = build_sector_js_data(cr_full, company_order, metrics=CR_METRICS + CR_BAR_ONLY_METRICS)
    js_data["nameSuffix"] = SECTOR_NAME_SUFFIX.get(sector, "")
    rated = load_rated_companies(company_order)
    js_data["rated"] = rated
    data_script = (f'<script type="application/json" id="data-{sector_key}">'
                    f'{json.dumps(js_data, ensure_ascii=False, separators=(",", ":"))}</script>')

    metric_options = "".join(f'<option value="{m}">{m}</option>' for m in CR_METRICS + CR_BAR_ONLY_METRICS)
    quarter_options = "".join(
        f'<option value="{q}"{" selected" if i == len(js_data["quarters"]) - 1 else ""}>{q}</option>'
        for i, q in enumerate(js_data["quarters"])
    )
    listed = rated or company_order   # 등급보유 목록이 없으면 전체 회사로 대체
    company_options = "".join(f"<option value=\"{c}\">" for c in listed)
    default_company = listed[0] if listed else ""
    bar_note = (f'<p class="caption">신평사 유효등급 보유 {len(rated)}개사 기준이에요 (2026.6월 기준). '
                '회사 선택 검색창에서는 그 외 회사도 검색해서 볼 수 있어요.</p>') if rated else ""
    bar_note += f'<p class="caption">{CR_BAR_NOTE}</p>'

    bar_section = (
        '<h4>회사별 지표 비교</h4>'
        '<div class="control-row">'
        '<label>지표 '
        f'<select id="crMetricSelect-{sector_key}" onchange="onCrChange(\'{sector_key}\')">{metric_options}</select></label>'
        '<label>기준 분기 '
        f'<select id="crQuarterSelect-{sector_key}" onchange="onCrChange(\'{sector_key}\')">{quarter_options}</select></label>'
        '</div>'
        f'{bar_note}'
        f'<div id="crBarChart-{sector_key}" class="plotly-chart"></div>'
    )

    range_btns = "".join(
        f'<button data-preset="{p}" onclick="{"toggleCrCustom" if p == "설정" else "applyCrPeriod"}'
        f'(\'{sector_key}\'{"" if p == "설정" else f",\'{p}\'"},this)">{p}</button>'
        for p in RANGE_PRESETS
    )
    controls = (
        '<h4>회사별 추이</h4>'
        '<div class="control-row">'
        '<label>회사 선택(검색 가능) '
        f'<input type="text" id="crCompanySelect-{sector_key}" list="crCompanyList-{sector_key}" '
        f'value="{default_company}" autocomplete="off" '
        f'onfocus="crCrFocus(\'{sector_key}\',this)" onblur="crCompanyBlur(\'{sector_key}\',this)" '
        f'oninput="crCrInput(\'{sector_key}\',this)"></label>'
        f'<datalist id="crCompanyList-{sector_key}">{company_options}</datalist>'
        '</div>'
        f'<div class="period-bar" data-scope="{sector_key}">'
        f'<span class="period-label">기간</span>{range_btns}</div>'
        f'<div class="custom-range" id="{sector_key}-customBox">'
        f'<input type="text" id="{sector_key}-start" placeholder="2018.Q1" style="width:90px;"> ~ '
        f'<input type="text" id="{sector_key}-end" placeholder="2026.Q2" style="width:90px;"> '
        f'<button onclick="applyCrCustomRange(\'{sector_key}\')">적용</button></div>'
    )

    # 한 줄에 너무 길면 추세가 안 보여서 2열 그리드로 배치
    trend_sections = (
        '<div class="grid" style="grid-template-columns:1fr 1fr;">' +
        "".join(
            f'<div class="cell"><h4>{m}</h4><div id="crTrend-{sector_key}-{i}" class="plotly-chart"></div></div>'
            for i, m in enumerate(CR_METRICS)
        ) + '</div>'
    )

    scatter_section = render_scatter_section(sector)

    return (
        CR_NOTE + data_script + bar_section + scatter_section + controls + trend_sections +
        f'<script>initCrSector("{sector_key}");</script>'
    )


# ================================================================ 재무제표형 탭 (손익계산서 / 대차대조표)
STMT_START_YM = 201703          # 전년동기 비교가 2018년부터 되도록 2017년부터 내장
STMT_ALL_LABEL = "저축은행 전체"

# kind별 설정. tables = (태그, 통계표코드, 항목). 태그는 코드 충돌 방지용 접두어
# (재무상태표는 자산/부채및자본 두 표가 둘 다 'A'로 시작).
STMT_KINDS = {
    "is": {
        "tables": [("", "SE006", "당분기")],
        "base": "A", "baseLabel": "영업수익 대비",
        "headline": ["A", "B", "C", "D", "E", "I", "J", "K"],
        "title": "요약손익계산서",
    },
    "bs": {
        "tables": [("a_", "SE003", "금액"), ("l_", "SE004", "금액")],
        "base": "a_A", "baseLabel": "총자산 대비",
        "headline": ["a_A", "l_A", "l_A1", "l_A2"],
        "title": "요약재무상태표",
    },
}


def _clean_stmt_name(raw: str) -> str:
    """'이자수익_대출금이자_계 급 부 이 익' -> '계급부이익' (마지막 구간만, 글자 사이 공백 제거)"""
    last = str(raw).split("_")[-1].strip()
    if last.startswith("("):  # '(당 좌 예 치 금)', '(C P)' 처럼 괄호 안은 공백 제거
        return last.replace(" ", "")
    tokens = last.split()
    if len(tokens) > 1 and all(len(t) == 1 for t in tokens):
        return "".join(tokens)
    return last


# FISIS 원본 구분명이 잘못 붙은 코드의 부모 보정 (코드상 만기보유증권(A23) 하위인데 이름은 매도가능증권으로 돼 있음)
PARENT_OVERRIDES = {"a_A234": "a_A23"}


def _name_path(raw: str) -> tuple:
    """구분 문자열을 계층 경로로. 공백 제거, '무형자산(기타)'처럼 괄호가 붙어 있으면 '_(' 로 분리."""
    s = re.sub(r"(?<=[^_(])\(", "_(", str(raw))
    return tuple(seg.replace(" ", "") for seg in s.split("_") if seg.strip())


def _build_tree(entries: list[dict]) -> list[dict]:
    """entries: {id, raw, code}. 부모는 1) 이름 경로(상위 경로와 일치하는 항목), 2) 없으면 코드 접두어
    (가장 가까운 존재하는 상위 코드) 순으로 찾고, 부모 뒤에 자식이 오는 DFS 순서 + depth를 반환."""
    by_path, by_code = {}, {}
    for e in entries:
        e["path"] = _name_path(e["raw"])
        by_path.setdefault(e["path"], e["id"])
        by_code[(e["tag"], e["code"])] = e["id"]
    for e in entries:
        parent = None
        for n in range(len(e["path"]) - 1, 0, -1):
            cand = by_path.get(e["path"][:n])
            if cand and cand != e["id"]:
                parent = cand
                break
        if parent is None:
            for n in range(len(e["code"]) - 1, 0, -1):
                cand = by_code.get((e["tag"], e["code"][:n]))
                if cand:
                    parent = cand
                    break
        e["parent"] = PARENT_OVERRIDES.get(e["id"], parent)
    children = {}
    for e in entries:
        children.setdefault(e["parent"], []).append(e)
    ordered = []

    def walk(parent_id, depth, seen):
        for e in sorted(children.get(parent_id, []), key=lambda x: (x["tag"], x["code"])):
            if e["id"] in seen:
                continue
            e["depth"] = depth
            ordered.append(e)
            walk(e["id"], depth + 1, seen | {e["id"]})

    walk(None, 0, set())
    return ordered


def build_statement_data(sector: str, kind: str) -> dict | None:
    """final_df의 재무제표 통계표(SE006 손익 / SE003·SE004 재무상태)를 회사 x 코드 x 분기 JSON으로 변환.
    값은 백만원 정수로 줄여서 내장하고(용량), 누계/전체합계는 브라우저에서 계산한다."""
    cfg = STMT_KINDS[kind]
    path = latest_final_df_path(sector)
    if path is None:
        return None
    df = pd.read_csv(path, index_col=0, encoding="cp949", low_memory=False)
    qcols = [c for c in df.columns if re.fullmatch(r"\d{6}", str(c)) and int(c) >= STMT_START_YM]
    if not qcols:
        return None

    entries, series, rev_idx = [], {}, {}
    for tag, table_code, item in cfg["tables"]:
        t = df[(df["통계표코드"].astype(str) == table_code) & (df["항목"] == item)].copy()
        if t.empty:
            continue
        for c in qcols:
            t[c] = pd.to_numeric(t[c], errors="coerce")
        # 코드별 표시명: 가장 최근 분기에 값이 있던 행의 이름
        for code, g in t.groupby("코드"):
            m = g[qcols].notna().values
            last = np.where(m.any(axis=1), m.shape[1] - 1 - np.argmax(m[:, ::-1], axis=1), -1)
            row = g.iloc[int(last.argmax())]
            entries.append({"id": tag + code, "tag": tag, "code": code, "raw": row["구분"]})
        for company, g in t.groupby("금융회사명"):
            # 같은 코드에 구분명이 바뀐 행이 둘 이상 있으면(예: 차입금이자 -> 차입부채이자) 분기별로
            # 값이 있는 쪽을 합쳐야 함 (drop_duplicates는 값이 빈 구버전 행을 남겨서 데이터가 사라짐)
            g = g.groupby("코드")[qcols].first()
            per = series.setdefault(company, {})
            for code in g.index:
                arr = g.loc[code, qcols].astype(float)
                if arr.notna().sum() == 0 or (arr.fillna(0) == 0).all():
                    continue  # 전 기간 값이 없거나 늘 0인 코드는 내장하지 않음(용량)
                per[tag + code] = [None if pd.isna(v) else int(round(v / 1e6)) for v in arr]
    series = {c: p for c, p in series.items() if p}
    if not series:
        return None

    used = {i for per in series.values() for i in per}
    entries = [e for e in entries if e["id"] in used]
    ordered = _build_tree(entries)
    codes = [{"code": e["id"], "name": _clean_stmt_name(e["raw"]), "depth": e["depth"], "parent": e["parent"]}
             for e in ordered]

    # 최신 분기 기준 크기(base 코드) 큰 순 - 공시가 끊긴 회사는 뒤로
    def size_key(name):
        arr = series[name].get(cfg["base"]) or []
        idx = [i for i, v in enumerate(arr) if v is not None]
        return (idx[-1], arr[idx[-1]]) if idx else (-1, 0)

    companies = sorted(series, key=size_key, reverse=True)

    child_ids = {}
    for c in codes:
        child_ids.setdefault(c["parent"], []).append(c["code"])
    if kind == "is":
        pies = [
            {"title": "영업수익 구성", "ids": child_ids.get("A", []),
             "colors": ["#2980B9", "#5DADE2", "#85C1E9", "#AED6F1", "#1F618D", "#7FB3D5"]},
            {"title": "영업비용 구성", "ids": child_ids.get("B", []),
             "colors": ["#E67E73", "#F1948A", "#F5B7B1", "#CD6155", "#EC7063", "#D98880"]},
        ]
    else:
        pies = [
            {"title": "자산 구성", "ids": child_ids.get("a_A", []),
             "colors": ["#2980B9", "#5DADE2", "#85C1E9", "#AED6F1", "#1F618D", "#7FB3D5"]},
            {"title": "부채 및 자본 구성", "ids": child_ids.get("l_A1", []) + ["l_A2"],
             "colors": ["#E67E73", "#F1948A", "#F5B7B1", "#CD6155", "#34495E", "#D98880"]},
        ]
    return {
        "kind": kind,
        "quarters": [format_ym(int(q)) for q in qcols],
        "companies": companies,
        "codes": codes,
        "series": series,
        "allLabel": STMT_ALL_LABEL,
        "headline": cfg["headline"],
        "base": cfg["base"],
        "pies": pies,
    }


def render_statement_tab(sector_key: str, sector: str, kind: str) -> str:
    cfg = STMT_KINDS[kind]
    data = build_statement_data(sector, kind)
    if data is None:
        return '<p class="caption">아직 수집된 데이터가 없어요.</p>'
    payload = (f'<script type="application/json" id="data-{sector_key}">'
               f'{json.dumps(data, ensure_ascii=False, separators=(",", ":"))}</script>')
    last_i = len(data["quarters"]) - 1
    quarter_options = "".join(
        f'<option value="{i}"{" selected" if i == last_i else ""}>{data["quarters"][i]}</option>'
        for i in range(last_i, -1, -1)
    )
    company_options = "".join(f'<option value="{c}">' for c in [STMT_ALL_LABEL] + data["companies"])
    basis_ctl = ""
    if kind == "is":  # 재무상태표는 시점 잔액이라 당분기/누계 구분이 없음
        basis_ctl = (
            '<label>구분 '
            f'<select id="isBasis-{sector_key}" onchange="onIsChange(\'{sector_key}\')" style="min-width:120px;">'
            '<option value="q">당분기</option><option value="cum">누계(연초~)</option></select></label>'
        )
    controls = (
        '<div class="control-row">'
        '<label>회사(검색 가능) '
        f'<input type="text" id="isCompany-{sector_key}" list="isCompanyList-{sector_key}" '
        f'value="{STMT_ALL_LABEL}" autocomplete="off" '
        f'onfocus="crCompanyFocus(this)" onblur="isCompanyBlur(\'{sector_key}\',this)" '
        f'oninput="onIsChange(\'{sector_key}\')"></label>'
        f'<datalist id="isCompanyList-{sector_key}">{company_options}</datalist>'
        '<label>기준 분기 '
        f'<select id="isQuarter-{sector_key}" onchange="onIsChange(\'{sector_key}\')" style="min-width:120px;">'
        f'{quarter_options}</select></label>'
        f'{basis_ctl}'
        '</div>'
        f'<p class="caption" id="isCaption-{sector_key}"></p>'
    )
    main_title = "손익 흐름" if kind == "is" else "자산 vs 부채 및 자본"
    pie_title = "수익 / 비용 구성" if kind == "is" else "자산 / 부채 및 자본 구성 비중 (업권 전체 vs 선택 회사)"
    body = (
        f'<h4>{main_title}</h4>'
        f'<div id="isMain-{sector_key}" class="plotly-chart"></div>'
        f'<h4>{pie_title}</h4>'
        '<div class="grid" style="grid-template-columns:1fr 1fr;">'
        f'<div class="cell"><div id="isPie0-{sector_key}" class="plotly-chart"></div></div>'
        f'<div class="cell"><div id="isPie1-{sector_key}" class="plotly-chart"></div></div>'
        '</div>'
        f'<h4>{cfg["title"]} <span class="caption" style="font-weight:normal;">(단위: 억원 · ▼/▶를 눌러 세부 항목 접기/펼치기)</span></h4>'
        f'<div style="overflow-x:auto;"><table class="data-table is-table" id="isTable-{sector_key}">'
        f'<thead><tr><th>항목</th><th>금액</th><th>{cfg["baseLabel"]}</th>'
        '<th class="is-qoq">전분기</th><th class="is-qoq">전분기대비</th>'
        '<th>전년동기</th><th>전년동기대비</th></tr></thead>'
        f'<tbody id="isBody-{sector_key}"></tbody></table></div>'
    )
    return payload + controls + body + f'<script>initIsSector("{sector_key}");</script>'


# ================================================================ 수익성 탭: ROA vs 기준금리
INFOMAX_XLSX = REPO_DIR / "output" / "Infomax_데이터.xlsx"


def load_base_rate_quarterly() -> pd.Series:
    """인포맥스 엑셀(월별)에서 '한국:기준금리'를 분기말(3/6/9/12월) 값으로 뽑아 {'2026.Q3': 3.0} 형태로 반환.
    엑셀 구조: 2행(인덱스1)=지표명, 4행부터 데이터, 첫 열=일자."""
    if not INFOMAX_XLSX.exists():
        return pd.Series(dtype=float)
    raw = pd.read_excel(INFOMAX_XLSX, header=None)
    names = raw.iloc[1].tolist()
    col = next((i for i, n in enumerate(names) if str(n).strip() == "한국:기준금리"), None)
    if col is None:
        return pd.Series(dtype=float)
    if col == 0:   # 첫 지표는 헤더 이름이 일자 열(0열)에, 단위("단위: %")가 데이터 열(1열) 머리에 들어 있음
        col = 1
    d = raw.iloc[3:, [0, col]].copy()
    d.columns = ["일자", "금리"]
    d["일자"] = pd.to_datetime(d["일자"], errors="coerce")
    d["금리"] = pd.to_numeric(d["금리"], errors="coerce")
    d = d.dropna(subset=["일자", "금리"])
    d["ym"] = d["일자"].dt.year * 100 + d["일자"].dt.month
    d = d[d["일자"].dt.month.isin([3, 6, 9, 12])].drop_duplicates(subset="ym", keep="last")
    # 월 중간(예: 10월 6일) 같은 부분월 행은 분기말이 아니라 위 필터에서 자연히 제외됨
    d = d[d["일자"] == d["일자"] + pd.offsets.MonthEnd(0)]
    return pd.Series(d["금리"].to_numpy(), index=[format_ym(int(v)) for v in d["ym"]])


def industry_roa_series(long_df: pd.DataFrame) -> pd.DataFrame:
    """업권 전체 ROA(%) - 분기 연율화(당기순이익 x4 / 총자산 분기 평잔)와 4분기누적. 회사별로 값을 구한 뒤
    분자/분모를 각각 합산 (직전 분기 자산이 없는 회사는 그 분기 합산에서 제외)."""
    cr = build_credit_rating_table(long_df)
    frames = []
    for _, g in cr.groupby("금융회사명"):
        g = g.sort_values("년월").reset_index(drop=True)
        avg2 = (g["자산총계"] + g["자산총계"].shift(1)) / 2
        avg5 = g["자산총계"].rolling(5, min_periods=5).mean()
        ni4 = g["당기순이익"].rolling(4, min_periods=4).sum()
        frames.append(pd.DataFrame({
            "년월": g["년월"], "ni": g["당기순이익"], "avg2": avg2, "ni4": ni4, "avg5": avg5}))
    f = pd.concat(frames, ignore_index=True)
    q = f.dropna(subset=["ni", "avg2"]).groupby("년월")[["ni", "avg2"]].sum()
    y = f.dropna(subset=["ni4", "avg5"]).groupby("년월")[["ni4", "avg5"]].sum()
    out = pd.DataFrame({"ROA": q["ni"] * 4 / q["avg2"] * 100, "ROA4": y["ni4"] / y["avg5"] * 100})
    return out.sort_index()


def render_profitability_tab(kis_payload: dict, sector_key: str) -> str:
    rate = load_base_rate_quarterly()
    all_series = (kis_payload or {}).get("series", {}).get(kis_charts.ALL_LABEL, {})
    roa_vals, roa4_vals = all_series.get("pf_roa"), all_series.get("pf_roa4")
    if rate.empty or not roa_vals:
        return '<p class="caption">기준금리 또는 ROA 데이터가 없어요.</p>'
    quarters = kis_payload["quarters"]
    roa = pd.DataFrame({"ROA": roa_vals, "ROA4": roa4_vals or [None] * len(quarters)}, index=quarters)
    # ROA가 있는 전 기간을 표시하고, 기준금리(인포맥스 엑셀)는 데이터가 있는 구간에만 그린다
    labels = [q for q in quarters if not pd.isna(roa["ROA"].get(q))]
    rate = rate.reindex(labels)
    nn = lambda v: None if v is None or pd.isna(v) else round(float(v), 4)
    data = {
        "labels": labels,
        "roa": [nn(roa["ROA"].get(q)) for q in labels],
        "roa4": [nn(roa["ROA4"].get(q)) for q in labels],
        "rate": [nn(v) for v in rate.tolist()],
    }
    scope = f"{sector_key}-prof"
    payload = (f'<script type="application/json" id="data-{scope}">'
               f'{json.dumps(data, ensure_ascii=False, separators=(",", ":"))}</script>')
    presets = ["1Y", "3Y", "5Y", "전체", "설정"]
    btns = "".join(
        f'<button data-preset="{p}" onclick="{"profCustomToggle" if p == "설정" else "profPreset"}'
        f'(\'{scope}\'{"" if p == "설정" else f",\'{p}\'"},this)">{p}</button>'
        for p in presets
    )
    note = ('<p class="caption">저축은행 업권 전체 ROA = 회사별 당기순이익(당분기) ×4 ÷ 총자산 분기 평잔을 업권 합산한 값이에요 '
            '(4분기누적은 범례를 눌러 켜세요). 기준금리는 인포맥스 데이터의 분기말 값이고 우축은 역축(위쪽이 낮은 금리)이에요.</p>')
    controls = (
        f'<div class="period-bar" data-scope="{scope}"><span class="period-label">기간</span>{btns}</div>'
        f'<div class="custom-range" id="{scope}-customBox">'
        f'<input type="text" id="{scope}-start" placeholder="2020.Q1" style="width:90px;"> ~ '
        f'<input type="text" id="{scope}-end" placeholder="2026.Q2" style="width:90px;"> '
        f'<button onclick="profCustomApply(\'{scope}\')">적용</button></div>'
    )
    return (
        '<h4>ROA와 기준금리</h4>' + note + payload + controls +
        '<div class="grid" style="grid-template-columns:1fr 1fr;">'
        f'<div class="cell"><div id="profChart-{scope}" class="plotly-chart"></div></div>'
        '<div class="cell"></div>'
        '</div>'
        f'<script>initProf("{scope}");</script>'
    )


def render_placeholder_tab(label: str) -> str:
    return f'<p class="caption">"{label}" 탭은 준비 중이에요. 곧 채워질 예정입니다.</p>'


def render_savings_bank_page(sector_key: str, sector: str) -> str:
    long_df = load_sector_long(sector)
    kpi = build_kpi_table(long_df)
    if kpi.empty or kpi["당기순이익"].dropna().empty:
        empty = '<p class="caption">아직 수집된 데이터가 없어요.</p>'
        bodies = [empty, empty] + [render_placeholder_tab(lbl) for lbl in SAVINGS_BANK_TABS[2:]]
        return tabs_html(SAVINGS_BANK_TABS, bodies)

    snap_full = latest_snapshot_full(kpi)
    company_order = snap_full["금융회사명"].tolist()  # 당기순이익 내림차순, 두 탭 공통 정렬 기준
    cr_content = render_credit_rating_tab(f"{sector_key}-cr", sector, kpi, company_order)
    perf_content = render_main_tab_rich(f"{sector_key}-perf", sector, kpi, snap_full)

    rated = load_rated_companies(company_order)
    kis_payload = kis_charts.build_kis_payload(sector, rated)
    stmt_kind = {"손익계산서": ("is", "is"), "대차대조표": ("bs", "bs")}
    rest = [
        render_statement_tab(f"{sector_key}-{stmt_kind[lbl][0]}", sector, stmt_kind[lbl][1])
        if lbl in stmt_kind
        else render_profitability_tab(kis_payload, sector_key) if lbl == "수익성"
        else render_placeholder_tab(lbl)
        for lbl in SAVINGS_BANK_TABS[2:]
    ]
    bodies = [cr_content, perf_content] + rest

    # 저축은행 Data Package(SBI 탭 기준) 항목 차트: 서브탭 하단에 붙임
    if kis_payload:
        bodies = [b + kis_charts.render_kis_block(lbl) for b, lbl in zip(bodies, SAVINGS_BANK_TABS)]
        return tabs_html(SAVINGS_BANK_TABS, bodies) + kis_charts.render_kis_data_script(kis_payload)
    return tabs_html(SAVINGS_BANK_TABS, bodies)


CSS = """
:root { --accent:#2980B9; --border:#e5e7eb; --text:#222; --muted:#666; --bg:#fff; --side-bg:#f7f8fa; }
* { box-sizing: border-box; }
body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
       color:var(--text); background:var(--bg); }
#layout { display:flex; min-height:100vh; }
#sidebar { width:220px; flex:0 0 220px; background:var(--side-bg); border-right:1px solid var(--border);
           padding:16px 8px; position:sticky; top:0; height:100vh; overflow-y:auto; }
#sidebar .brand { font-size:13px; color:var(--muted); padding:4px 12px 14px; }
#sidebar a { display:flex; align-items:center; gap:10px; padding:9px 12px; border-radius:8px; color:var(--text);
             text-decoration:none; font-size:15px; margin-bottom:2px; }
#sidebar a:hover { background:#eceff3; }
#sidebar a.active { background:#e3edf7; color:var(--accent); font-weight:600; }
#main { flex:1; min-width:0; padding:0 32px 60px; }
#main h1 { font-size:28px; margin:0; padding:20px 0 10px; position:sticky; top:0;
           background:var(--bg); z-index:6; }
#top-note { color:var(--muted); font-size:13px; padding-top:16px; margin-bottom:-8px; }
.page { display:none; }
.page.active { display:block; }
.grid { display:grid; gap:16px; margin:10px 0; }
.cell { min-width:0; }
.plotly-chart { width:100%; }
.caption { color:var(--muted); font-size:13px; margin:4px 0 10px; }
.caption a { color:var(--accent); }
.data-table { width:100%; border-collapse:collapse; font-size:14px; margin:10px 0; }
.data-table th { text-align:right; padding:6px 8px; border-bottom:2px solid #333; white-space:nowrap; }
.data-table th:first-child, .data-table td:first-child { text-align:left; }
.data-table td { text-align:right; padding:5px 8px; border-bottom:1px solid #eee; white-space:nowrap; }
.kis-title { font-size:14px; font-weight:600; margin:10px 0 0; }
.kis-title span { font-weight:normal; color:var(--muted); font-size:12px; }
.is-table td:first-child { text-align:left; }
.is-table tr.is-head td { font-weight:700; background:#f7f8fa; }
.is-toggle { cursor:pointer; color:var(--accent); font-size:11px; display:inline-block; width:14px; }
.is-toggle-pad { display:inline-block; width:14px; }
.data-table th.sortable { cursor:pointer; user-select:none; }
.data-table th.sortable:hover { color:var(--accent); }
.sort-arrow { font-size:11px; color:var(--accent); }
.tabgroup { margin-top:0; }
.tab-bar { display:flex; gap:4px; border-bottom:2px solid var(--border); margin-bottom:16px;
           overflow-x:auto; flex-wrap:nowrap; position:sticky; top:58px; background:var(--bg); z-index:5; }
.tab-btn { border:none; background:none; padding:10px 14px; font-size:14px; cursor:pointer; color:var(--muted);
           border-bottom:2px solid transparent; margin-bottom:-2px; white-space:nowrap; }
.tab-btn:hover { color:var(--text); }
.tab-btn.active { color:var(--accent); border-bottom-color:var(--accent); font-weight:600; }
.tab-panel { display:none; }
.tab-panel.active { display:block; }
.control-row { margin:10px 0 16px; font-size:14px; display:flex; flex-wrap:wrap; gap:16px; }
.control-row label { display:flex; align-items:center; gap:8px; }
.control-row select, .control-row input { border:1px solid var(--border); border-radius:6px; padding:6px 10px;
                                           font-size:14px; min-width:220px; }
.period-bar { display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin:10px 0 16px;
              padding-bottom:12px; border-bottom:1px solid var(--border); }
.period-label { font-size:13px; color:var(--muted); margin-right:6px; }
.period-bar button { border:1px solid var(--border); background:#fff; border-radius:6px; padding:5px 11px;
                      font-size:13px; cursor:pointer; color:var(--text); }
.period-bar button:hover { background:#f2f4f7; }
.period-bar button.active { background:#fdecea; border-color:#e8a39b; color:#c0392b; font-weight:600; }
.custom-range { display:none; align-items:center; gap:6px; margin:-8px 0 16px; font-size:13px; }
.custom-range.show { display:flex; }
.custom-range input { border:1px solid var(--border); border-radius:6px; padding:4px 6px; font-size:13px; }
@media (max-width: 900px) {
  #sidebar { position:fixed; left:-240px; transition:left .2s; z-index:20; box-shadow:2px 0 8px rgba(0,0,0,.1); }
  #sidebar.open { left:0; }
  #main { padding:16px; }
  .grid { grid-template-columns:1fr !important; }
}
"""

JS = """
function resizeCharts(root) {
  root.querySelectorAll('.plotly-chart').forEach(function(el){
    if (window.Plotly && el.data) window.Plotly.Plots.resize(el);
  });
}
function showPage(id) {
  document.querySelectorAll('.page').forEach(function(el){ el.classList.remove('active'); });
  document.querySelectorAll('#sidebar a').forEach(function(el){ el.classList.remove('active'); });
  var page = document.getElementById('page-' + id);
  page.classList.add('active');
  document.getElementById('nav-' + id).classList.add('active');
  window.scrollTo(0, 0);
  history.replaceState(null, '', '#' + id);
  setTimeout(function(){ resizeCharts(page.querySelector('.tab-panel.active') || page); if (window.kisRenderVisible) kisRenderVisible(); }, 0);
}
function showTab(groupId, idx) {
  var group = document.querySelector('[data-group="' + groupId + '"]');
  var btns = group.querySelectorAll('.tab-btn');
  var panels = group.querySelectorAll('.tab-panel');
  btns.forEach(function(b, i){ b.classList.toggle('active', i === idx); });
  panels.forEach(function(p, i){ p.classList.toggle('active', i === idx); });
  setTimeout(function(){ resizeCharts(panels[idx]); if (window.kisRenderVisible) kisRenderVisible(); }, 0);
}
function renderChart(id) {
  var payload = JSON.parse(document.getElementById(id + '-data').textContent);
  Plotly.newPlot(id, payload.data, payload.layout, {displaylogo:false, responsive:true});
}

var SECTOR_DATA = {};
var SORT_STATE = {};

function shortName(sector, name) {
  var data = SECTOR_DATA[sector];
  if (data.nameSuffix && name.indexOf(data.nameSuffix) !== -1) {
    return name.split(data.nameSuffix).join('');
  }
  return name;
}

function initSectorMain(sector) {
  var el = document.getElementById('data-' + sector);
  if (!el) return;
  SECTOR_DATA[sector] = JSON.parse(el.textContent);
  SORT_STATE[sector] = {key: 'netIncome', dir: -1};
  renderBarChart(sector);
  renderTrendCharts(sector);
  renderTable(sector);
}
function onQuarterChange(sector) { renderBarChart(sector); }
function onCompanyChange(sector) { renderTrendCharts(sector); }

function renderBarChart(sector) {
  var data = SECTOR_DATA[sector];
  if (!data) return;
  var q = document.getElementById('quarterSelect-' + sector).value;
  var qIdx = data.quarters.indexOf(q);
  var pairs = data.companies
    .map(function(c){ return [shortName(sector, c), data.series[c]['당기순이익'][qIdx]]; })
    .filter(function(p){ return p[1] !== null && p[1] !== undefined; })
    .map(function(p){ return [p[0], p[1] / 1e8]; });
  pairs.sort(function(a, b){ return b[1] - a[1]; });
  var x = pairs.map(function(p){ return p[0]; });
  var y = pairs.map(function(p){ return p[1]; });
  plotReact('barChart-' + sector, [{x:x, y:y, type:'bar', marker:{color:'#2980B9'}}], {
    height:440, margin:{t:20, b:140}, xaxis:{tickangle:-45}, yaxis:{title:'당기순이익(억원)'}
  }, {displaylogo:false, responsive:true});
}

function renderTrendCharts(sector) {
  var data = SECTOR_DATA[sector];
  if (!data) return;
  var company = document.getElementById('companySelect-' + sector).value;
  if (data.companies.indexOf(company) === -1) return;
  var startYear = parseInt(document.getElementById('rangeSelect-' + sector).value, 10);
  var idx = data.quarters.map(function(q, i){ return i; })
    .filter(function(i){ return startYear === 0 || parseInt(data.quarters[i].split('.')[0], 10) >= startYear; });
  var quarters = idx.map(function(i){ return data.quarters[i]; });
  var s = data.series[company];
  var pick = function(arr){ return idx.map(function(i){ return arr[i]; }); };

  plotReact('trendNI-' + sector, [{x:quarters, y:pick(s['당기순이익']), type:'bar', marker:{color:'#2980B9'}}], {
    height:360, margin:{t:40}, title:company + ' 당기순이익 추이', yaxis:{title:'당기순이익(원)'}
  }, {displaylogo:false, responsive:true});

  var traces = [];
  if (s['ROE'].some(function(v){ return v !== null; }))
    traces.push({x:quarters, y:pick(s['ROE']), mode:'lines+markers', name:'ROE', connectgaps:true,
                 line:{color:'#2980B9'}, yaxis:'y'});
  if (s['ROA'].some(function(v){ return v !== null; }))
    traces.push({x:quarters, y:pick(s['ROA']), mode:'lines+markers', name:'ROA', connectgaps:true,
                 line:{color:'#E67E22'}, yaxis:'y2'});
  plotReact('trendRoaRoe-' + sector, traces, {
    height:360, margin:{t:40, r:50}, title:company + ' ROA / ROE 추이',
    yaxis:{title:'ROE(%)'}, yaxis2:{title:'ROA(%)', overlaying:'y', side:'right'},
    legend:{orientation:'h', y:-0.2}
  }, {displaylogo:false, responsive:true});
}

var TABLE_COLS = ["revenue","opIncome","opMargin","opYoy","netIncome","netMargin","netYoy","roa","roe"];
var TABLE_FMT = {
  revenue:'eok', opIncome:'eok', opMargin:'pct', opYoy:'pct',
  netIncome:'eok', netMargin:'pct', netYoy:'pct', roa:'pct', roe:'pct'
};
function fmtCell(kind, v) {
  if (v === null || v === undefined) return '-';
  if (kind === 'eok') return (v / 1e8).toLocaleString('ko-KR', {maximumFractionDigits:0}) + '억원';
  return v.toFixed(2) + '%';
}
function sortTable(sector, key) {
  var st = SORT_STATE[sector];
  if (st.key === key) st.dir = -st.dir; else { st.key = key; st.dir = key === 'company' ? 1 : -1; }
  renderTable(sector);
}
function renderTable(sector) {
  var data = SECTOR_DATA[sector];
  var rows = data.tableRows.slice();
  var st = SORT_STATE[sector];
  rows.sort(function(a, b){
    var av = st.key === 'company' ? a.company : a[st.key];
    var bv = st.key === 'company' ? b.company : b[st.key];
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    if (av < bv) return -1 * st.dir;
    if (av > bv) return 1 * st.dir;
    return 0;
  });
  var tbody = document.getElementById('tbody-' + sector);
  tbody.innerHTML = rows.map(function(r, i){
    var cells = '<td>' + (i + 1) + '</td><td>' + r.company + '</td>';
    TABLE_COLS.forEach(function(key){ cells += '<td>' + fmtCell(TABLE_FMT[key], r[key]) + '</td>'; });
    return '<tr>' + cells + '</tr>';
  }).join('');
  ['company'].concat(TABLE_COLS).forEach(function(key){
    var arrow = document.getElementById('arrow-' + sector + '-' + key);
    if (arrow) arrow.textContent = (st.key === key) ? (st.dir === 1 ? '▲' : '▼') : '';
  });
}

var CR_RANGE = {};

function initCrSector(sector) {
  var el = document.getElementById('data-' + sector);
  if (!el) return;
  SECTOR_DATA[sector] = JSON.parse(el.textContent);
  CR_RANGE[sector] = {preset: '5Y', start: null, end: null};
  renderCrBarChart(sector);
  var btn = document.querySelector('.period-bar[data-scope="' + sector + '"] button[data-preset="5Y"]');
  applyCrPeriod(sector, '5Y', btn);
}
function onCrChange(sector) { renderCrBarChart(sector); renderAllCrTrends(sector); }

// emptyChartMsg가 넣어둔 안내 문구가 남아 있으면 지우고 그려야 차트가 문구 위에 겹쳐 그려지지 않음
function plotReact(id, data, layout, cfg) {
  var el = document.getElementById(id);
  if (el.querySelector('p.caption')) el.innerHTML = '';
  // 기본 스타일: 흰 배경, 가로(y축) 그리드만 (차트별로 지정한 값이 있으면 그걸 우선)
  layout = Object.assign({plot_bgcolor: 'white', paper_bgcolor: 'white'}, layout || {});
  layout.xaxis = Object.assign({showgrid: false}, layout.xaxis || {});
  layout.yaxis = Object.assign({showgrid: true, gridcolor: '#e5e7eb'}, layout.yaxis || {});
  return Plotly.react(id, data, layout, cfg);
}
function emptyChartMsg(id, msg) {
  var el = document.getElementById(id);
  if (window.Plotly) Plotly.purge(el);
  el.innerHTML = '<p class="caption" style="padding:40px 0;text-align:center;">' + msg + '</p>';
}

function renderCrBarChart(sector) {
  var data = SECTOR_DATA[sector];
  if (!data) return;
  var metric = document.getElementById('crMetricSelect-' + sector).value;
  var q = document.getElementById('crQuarterSelect-' + sector).value;
  var qIdx = data.quarters.indexOf(q);
  var barCompanies = (data.rated && data.rated.length) ? data.rated : data.companies;
  var pairs = barCompanies
    .map(function(c){ return [shortName(sector, c), data.series[c][metric][qIdx]]; })
    .filter(function(p){ return p[1] !== null && p[1] !== undefined; });
  var elId = 'crBarChart-' + sector;
  if (pairs.length === 0) {
    emptyChartMsg(elId, '이 분기엔 ' + metric + ' 데이터가 없어요. 다른 분기를 선택해보세요.');
    return;
  }
  pairs.sort(function(a, b){ return b[1] - a[1]; });
  plotReact(elId, [{
    x:pairs.map(function(p){ return p[0]; }), y:pairs.map(function(p){ return p[1]; }),
    type:'bar', marker:{color:'#2980B9'}
  }], {
    height:440, margin:{t:20, b:140}, xaxis:{tickangle:-45}, yaxis:{title:metric + ' (%)'}
  }, {displaylogo:false, responsive:true});
}

// 회사 검색창: 포커스하면 입력값을 비워서(복원용으로 저장) datalist 전체 목록이 보이게 함
function crCompanyFocus(el) {
  el.dataset.prev = el.value;
  el.value = '';
}
// 주요 지표 탭 회사 검색창: 비어 있을 땐 신평사 유효등급 보유 회사만, 글자를 입력하면 전체 회사에서 검색
function crFillList(sector, all) {
  var data = SECTOR_DATA[sector];
  var list = document.getElementById('crCompanyList-' + sector);
  var names = (all || !(data.rated && data.rated.length)) ? data.companies : data.rated;
  list.innerHTML = names.map(function(c){ return '<option value="' + c + '">'; }).join('');
}
function crCrFocus(sector, el) {
  crCompanyFocus(el);
  crFillList(sector, false);
}
function crCrInput(sector, el) {
  crFillList(sector, el.value.length > 0);
  onCrChange(sector);
}
function crCompanyBlur(sector, el) {
  if (!el.value) el.value = el.dataset.prev || '';
  onCrChange(sector);
}

function quarterIndexFromEnd(quarters, nYears) {
  return Math.max(0, quarters.length - nYears * 4);
}
function crRangeIndices(sector) {
  var data = SECTOR_DATA[sector];
  var r = CR_RANGE[sector];
  var n = data.quarters.length;
  if (r.preset === '전체') return data.quarters.map(function(_, i){ return i; });
  if (r.preset === '설정' && r.start && r.end) {
    var s = data.quarters.indexOf(r.start), e = data.quarters.indexOf(r.end);
    if (s === -1 || e === -1) return data.quarters.map(function(_, i){ return i; });
    return data.quarters.map(function(_, i){ return i; }).filter(function(i){ return i >= s && i <= e; });
  }
  var years = {'1Y':1, '3Y':3, '5Y':5, '10Y':10}[r.preset] || 5;
  var start = quarterIndexFromEnd(data.quarters, years);
  return data.quarters.map(function(_, i){ return i; }).filter(function(i){ return i >= start; });
}
function applyCrPeriod(sector, preset, btn) {
  CR_RANGE[sector].preset = preset;
  var bar = document.querySelector('.period-bar[data-scope="' + sector + '"]');
  bar.querySelectorAll('button').forEach(function(b){ b.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  document.getElementById(sector + '-customBox').classList.remove('show');
  renderAllCrTrends(sector);
}
function toggleCrCustom(sector, btn) {
  document.getElementById(sector + '-customBox').classList.toggle('show');
  var bar = document.querySelector('.period-bar[data-scope="' + sector + '"]');
  bar.querySelectorAll('button').forEach(function(b){ b.classList.remove('active'); });
  if (btn) btn.classList.add('active');
}
function applyCrCustomRange(sector) {
  var s = document.getElementById(sector + '-start').value.trim();
  var e = document.getElementById(sector + '-end').value.trim();
  if (!s || !e) return;
  CR_RANGE[sector] = {preset: '설정', start: s, end: e};
  renderAllCrTrends(sector);
}

function industryAverage(data, metric, idx) {
  return idx.map(function(i){
    var sum = 0, n = 0;
    data.companies.forEach(function(c){
      var v = data.series[c][metric][i];
      if (v !== null && v !== undefined) { sum += v; n += 1; }
    });
    return n ? sum / n : null;
  });
}

function renderAllCrTrends(sector) {
  CR_METRICS_JS.forEach(function(m, i){ renderCrTrend(sector, i, m); });
}
function renderCrTrend(sector, i, metric) {
  var data = SECTOR_DATA[sector];
  var company = document.getElementById('crCompanySelect-' + sector).value;
  var elId = 'crTrend-' + sector + '-' + i;
  if (data.companies.indexOf(company) === -1) {
    emptyChartMsg(elId, '회사를 선택해주세요.');
    return;
  }
  var idx = crRangeIndices(sector);
  var quarters = idx.map(function(j){ return data.quarters[j]; });
  var avgVals = industryAverage(data, metric, idx);
  var companyVals = idx.map(function(j){ return data.series[company][metric][j]; });
  if (avgVals.every(function(v){ return v === null; }) && companyVals.every(function(v){ return v === null; })) {
    emptyChartMsg(elId, '이 기간엔 ' + metric + ' 데이터가 없어요.');
    return;
  }
  plotReact(elId, [
    {x:quarters, y:avgVals, mode:'lines+markers', connectgaps:true, name:'업권 평균',
     line:{color:'#999', dash:'dot'}},
    {x:quarters, y:companyVals, mode:'lines+markers', connectgaps:true, name:shortName(sector, company),
     line:{color:'#2980B9', width:2.5}}
  ], {
    height:320, margin:{t:20}, yaxis:{title:metric + ' (%)'}, legend:{orientation:'h', y:-0.2}
  }, {displaylogo:false, responsive:true});
}

document.addEventListener('DOMContentLoaded', function() {
  var hash = location.hash.replace('#', '');
  var valid = document.getElementById('page-' + hash);
  showPage(valid ? hash : DEFAULT_PAGE);
});
/* ===================== 재무제표형 탭 (손익계산서 / 대차대조표) ===================== */
var IS_STATE = {};
var IS_INDENT_PX = 24;

function initIsSector(sector) {
  var el = document.getElementById('data-' + sector);
  if (!el) return;
  var data = JSON.parse(el.textContent);
  var parent = {}, children = {}, open = {};
  data.codes.forEach(function(c){
    if (c.parent) {
      parent[c.code] = c.parent;
      (children[c.parent] = children[c.parent] || []).push(c.code);
      open[c.parent] = true;   // 기본값: 모두 펼침
    }
  });
  var agg = {};
  data.codes.forEach(function(c){
    var arr = data.quarters.map(function(){ return null; });
    data.companies.forEach(function(co){
      var s = data.series[co][c.code];
      if (!s) return;
      for (var i = 0; i < s.length; i++) {
        if (s[i] !== null) arr[i] = (arr[i] || 0) + s[i];
      }
    });
    agg[c.code] = arr;
  });
  IS_STATE[sector] = {data: data, parent: parent, children: children, agg: agg, open: open};
  onIsChange(sector);
}

function isCompanyBlur(sector, el) {
  if (!el.value) el.value = el.dataset.prev || '';
  onIsChange(sector);
}

function isSeries(st, company, code) {
  if (company === st.data.allLabel) return st.agg[code] || null;
  var s = st.data.series[company];
  return s ? (s[code] || null) : null;
}

function isValue(st, company, code, idx, basis) {
  if (idx < 0) return null;
  var s = isSeries(st, company, code);
  if (!s) return null;
  if (basis === 'q') return s[idx];
  var qn = parseInt(st.data.quarters[idx].split('Q')[1], 10);
  var sum = null;
  for (var i = idx - (qn - 1); i <= idx; i++) {
    if (i >= 0 && s[i] !== null) sum = (sum || 0) + s[i];
  }
  return sum;
}

function fmtEokJs(v) {
  if (v === null || v === undefined) return '-';
  var e = v / 100;
  var d = Math.abs(e) >= 1000 ? 0 : 1;
  return e.toLocaleString('ko-KR', {minimumFractionDigits: d, maximumFractionDigits: d});
}
function fmtPctJs(v, signed) {
  if (v === null || v === undefined || !isFinite(v)) return '-';
  var s = v.toFixed(1) + '%';
  return (signed && v > 0) ? '+' + s : s;
}
function chgPct(cur, prev) {
  if (cur === null || prev === null || prev === 0) return null;
  return (cur - prev) / Math.abs(prev) * 100;
}

function onIsChange(sector) {
  var st = IS_STATE[sector];
  if (!st) return;
  var data = st.data;
  var input = document.getElementById('isCompany-' + sector);
  var company = input.value;
  if (company !== data.allLabel && !data.series[company]) return;  // 입력 중이거나 목록에 없는 이름
  st.company = company;
  st.idx = parseInt(document.getElementById('isQuarter-' + sector).value, 10);
  var basisEl = document.getElementById('isBasis-' + sector);
  st.basis = basisEl ? basisEl.value : 'q';   // 재무상태표는 시점 잔액이라 항상 'q'
  renderIsCaption(sector);
  if (data.kind === 'is') renderIsWaterfall(sector); else renderBsStack(sector);
  if (data.kind === 'bs') renderBsShare(sector); else renderIsPies(sector);
  renderIsTable(sector);
}

function isV(st, code, idx) { return isValue(st, st.company, code, idx, st.basis); }

function renderIsCaption(sector) {
  var st = IS_STATE[sector], data = st.data;
  var txt = st.company + ' · ' + data.quarters[st.idx];
  if (data.kind === 'is') txt += (st.basis === 'cum' ? ' 누계(연초~해당 분기)' : ' 당분기');
  if (st.company === data.allLabel) {
    var n = 0;
    data.companies.forEach(function(co){
      var s = data.series[co][data.base];
      if (s && s[st.idx] !== null) n++;
    });
    txt += ' · 해당 분기 공시 ' + n + '개사 합산';
  } else if (isV(st, data.base, st.idx) === null) {
    txt += ' · 해당 분기 데이터 없음';
  }
  document.getElementById('isCaption-' + sector).textContent = txt;
}

function renderIsWaterfall(sector) {
  var st = IS_STATE[sector];
  var id = 'isMain-' + sector;
  var g = function(c){ return isV(st, c, st.idx); };
  var A = g('A');
  if (A === null) { emptyChartMsg(id, '해당 분기 데이터가 없어요.'); return; }
  var nz = function(v){ return v === null ? 0 : v; };
  var labels = ['영업수익', '영업비용', '영업이익', '영업외수익', '영업외비용', '법인세', '당기순이익'];
  var vals = [A, -nz(g('B')), nz(g('C')), nz(g('D')), -nz(g('E')), -nz(g('J')), nz(g('K'))];
  var measure = ['absolute', 'relative', 'total', 'relative', 'relative', 'relative', 'total'];
  var y = vals.map(function(v){ return v / 100; });
  var trace = {
    type: 'waterfall', orientation: 'v', x: labels, y: y, measure: measure,
    text: vals.map(function(v){ return fmtEokJs(v); }), textposition: 'outside',
    connector: {line: {color: '#bbb'}},
    increasing: {marker: {color: '#2980B9'}}, decreasing: {marker: {color: '#E67E73'}},
    totals: {marker: {color: '#34495E'}},
    hovertemplate: '%{x}: %{y:,.1f}억원<extra></extra>'
  };
  plotReact(id, [trace], {
    height: 400, margin: {t: 20, r: 20, b: 40, l: 70}, yaxis: {title: '억원', tickformat: ','},
    showlegend: false
  }, {displaylogo: false, responsive: true});
}

function isCodeName(st, code) {
  for (var i = 0; i < st.data.codes.length; i++) {
    if (st.data.codes[i].code === code) return st.data.codes[i].name;
  }
  return code;
}

function renderBsStack(sector) {
  var st = IS_STATE[sector], data = st.data;
  var id = 'isMain-' + sector;
  if (isV(st, data.base, st.idx) === null) { emptyChartMsg(id, '해당 분기 데이터가 없어요.'); return; }
  var traces = [];
  data.pies.forEach(function(pie, col){
    pie.ids.forEach(function(code, k){
      var v = isV(st, code, st.idx);
      if (v === null || v <= 0) return;
      var y = [null, null];
      y[col] = v / 100;
      traces.push({
        type: 'bar', x: ['자산', '부채 및 자본'], y: y, name: isCodeName(st, code),
        marker: {color: pie.colors[k % pie.colors.length]},
        text: [col === 0 ? isCodeName(st, code) : '', col === 1 ? isCodeName(st, code) : ''],
        textposition: 'inside', insidetextanchor: 'middle',
        hovertemplate: '%{fullData.name}: %{y:,.0f}억원<extra></extra>'
      });
    });
  });
  plotReact(id, traces, {
    barmode: 'stack', height: 440, margin: {t: 20, r: 20, b: 40, l: 70},
    yaxis: {title: '억원', tickformat: ','}, showlegend: false
  }, {displaylogo: false, responsive: true});
}

function renderIsPies(sector) {
  var st = IS_STATE[sector], data = st.data;
  data.pies.forEach(function(pie, n){
    var id = 'isPie' + n + '-' + sector;
    var items = pie.ids.map(function(code){ return {name: isCodeName(st, code), v: isV(st, code, st.idx)}; })
      .filter(function(it){ return it.v !== null && it.v > 0; });
    if (!items.length) { emptyChartMsg(id, '해당 분기 데이터가 없어요.'); return; }
    plotReact(id, [{
      type: 'pie', hole: 0.45, labels: items.map(function(i){ return i.name; }),
      values: items.map(function(i){ return i.v / 100; }),
      textinfo: 'label+percent', sort: true, automargin: true, marker: {colors: pie.colors},
      hovertemplate: '%{label}: %{value:,.1f}억원 (%{percent})<extra></extra>'
    }], {
      title: {text: pie.title, font: {size: 15}}, height: 380, margin: {t: 50, r: 10, b: 10, l: 10}, showlegend: false
    }, {displaylogo: false, responsive: true});
  });
}


// 대차대조표: 업권 전체 vs 선택 회사의 구성 비중(100% 누적 막대). 전체를 고르면 업권 전체 한 개만 표시
function renderBsShare(sector) {
  var st = IS_STATE[sector], data = st.data;
  var entities = [data.allLabel];
  if (st.company !== data.allLabel) entities.push(st.company);
  var xLabels = entities.map(function(c){ return c === data.allLabel ? '업권 전체' : c; });
  data.pies.forEach(function(pie, n){
    var id = 'isPie' + n + '-' + sector;
    var vals = pie.ids.map(function(code){
      return entities.map(function(c){
        var v = isValue(st, c, code, st.idx, 'q');
        return (v === null || v <= 0) ? 0 : v;
      });
    });
    var totals = entities.map(function(_, e){
      return vals.reduce(function(sum, row){ return sum + row[e]; }, 0);
    });
    if (totals.every(function(t){ return t === 0; })) { emptyChartMsg(id, '해당 분기 데이터가 없어요.'); return; }
    var traces = [];
    pie.ids.forEach(function(code, k){
      var name = isCodeName(st, code);
      var pct = vals[k].map(function(v, e){ return totals[e] ? v / totals[e] * 100 : 0; });
      traces.push({
        type: 'bar', x: xLabels, y: pct, name: name,
        marker: {color: pie.colors[k % pie.colors.length]},
        text: pct.map(function(p){ return p >= 3 ? name + ' ' + p.toFixed(1) + '%' : ''; }),
        textposition: 'inside', insidetextanchor: 'middle', textfont: {size: 12},
        hovertemplate: '%{x}<br>' + name + ' %{y:.1f}%<extra></extra>'
      });
    });
    plotReact(id, traces, {
      barmode: 'stack', title: {text: pie.title, font: {size: 15}}, height: 420,
      margin: {t: 50, r: 10, b: 40, l: 50}, showlegend: false,
      yaxis: {range: [0, 100], ticksuffix: '%'}
    }, {displaylogo: false, responsive: true});
  });
}

function isHasData(st, code) {
  var a = isV(st, code, st.idx), b = isV(st, code, st.idx - 4);
  return (a !== null && a !== 0) || (b !== null && b !== 0);
}

function isVisible(st, c) {
  if (!isHasData(st, c.code) && st.data.headline.indexOf(c.code) === -1) return false;
  var p = st.parent[c.code];
  while (p) {
    if (!st.open[p]) return false;
    p = st.parent[p];
  }
  return true;
}

function toggleIsRow(sector, code) {
  var st = IS_STATE[sector];
  st.open[code] = !st.open[code];
  renderIsTable(sector);
}

function renderIsTable(sector) {
  var st = IS_STATE[sector], data = st.data;
  var cum = st.basis === 'cum';
  document.querySelectorAll('#isTable-' + sector + ' .is-qoq').forEach(function(el){
    el.style.display = cum ? 'none' : '';
  });
  var base = isV(st, data.base, st.idx);
  var html = [];
  data.codes.forEach(function(c){
    if (!isVisible(st, c)) return;
    var cur = isV(st, c.code, st.idx);
    var prevQ = isV(st, c.code, st.idx - 1);
    var prevY = isV(st, c.code, st.idx - 4);
    var kids = (st.children[c.code] || []).filter(function(k){ return isHasData(st, k); });
    var isHead = data.headline.indexOf(c.code) !== -1;
    var toggle = kids.length
      ? '<span class="is-toggle" onclick="toggleIsRow(\\'' + sector + '\\',\\'' + c.code + '\\')">' +
        (st.open[c.code] ? '▼' : '▶') + '</span> '
      : '<span class="is-toggle-pad"></span>';
    var pad = c.depth * IS_INDENT_PX;
    var share = (base !== null && base !== 0 && cur !== null) ? cur / base * 100 : null;
    html.push(
      '<tr class="' + (isHead ? 'is-head' : '') + '"><td style="padding-left:' + (8 + pad) + 'px;">' + toggle + c.name + '</td>' +
      '<td>' + fmtEokJs(cur) + '</td><td>' + fmtPctJs(share, false) + '</td>' +
      (cum ? '' : '<td>' + fmtEokJs(prevQ) + '</td><td>' + fmtPctJs(chgPct(cur, prevQ), true) + '</td>') +
      '<td>' + fmtEokJs(prevY) + '</td><td>' + fmtPctJs(chgPct(cur, prevY), true) + '</td></tr>'
    );
  });
  document.getElementById('isBody-' + sector).innerHTML = html.join('');
}

/* ===================== 수익성 탭: ROA vs 기준금리 ===================== */
var PROF = {};
function initProf(scope) {
  var el = document.getElementById('data-' + scope);
  if (!el) return;
  PROF[scope] = {d: JSON.parse(el.textContent), preset: '전체', start: null, end: null};
  var btn = document.querySelector('.period-bar[data-scope="' + scope + '"] button[data-preset="전체"]');
  if (btn) btn.classList.add('active');
  renderProf(scope);
}
function profIndices(scope) {
  var st = PROF[scope], n = st.d.labels.length;
  var all = st.d.labels.map(function(_, i){ return i; });
  if (st.preset === '설정' && st.start && st.end) {
    var s = st.d.labels.indexOf(st.start), e = st.d.labels.indexOf(st.end);
    if (s !== -1 && e !== -1) return all.filter(function(i){ return i >= s && i <= e; });
    return all;
  }
  var years = {'1Y': 1, '3Y': 3, '5Y': 5}[st.preset];
  if (!years) return all;
  var start = Math.max(0, n - years * 4);
  return all.filter(function(i){ return i >= start; });
}
function profPreset(scope, preset, btn) {
  PROF[scope].preset = preset;
  var bar = document.querySelector('.period-bar[data-scope="' + scope + '"]');
  bar.querySelectorAll('button').forEach(function(b){ b.classList.remove('active'); });
  if (btn) btn.classList.add('active');
  document.getElementById(scope + '-customBox').classList.remove('show');
  renderProf(scope);
}
function profCustomToggle(scope, btn) {
  document.getElementById(scope + '-customBox').classList.toggle('show');
  var bar = document.querySelector('.period-bar[data-scope="' + scope + '"]');
  bar.querySelectorAll('button').forEach(function(b){ b.classList.remove('active'); });
  if (btn) btn.classList.add('active');
}
function profCustomApply(scope) {
  var s = document.getElementById(scope + '-start').value.trim();
  var e = document.getElementById(scope + '-end').value.trim();
  if (!s || !e) return;
  PROF[scope].preset = '설정'; PROF[scope].start = s; PROF[scope].end = e;
  renderProf(scope);
}
function renderProf(scope) {
  var st = PROF[scope], d = st.d, id = 'profChart-' + scope;
  var idx = profIndices(scope);
  var pick = function(arr){ return idx.map(function(i){ return arr[i]; }); };
  var el = document.getElementById(id);
  var roa4Visible = (el.data && el.data[1]) ? el.data[1].visible : 'legendonly';  // 범례 토글 상태 유지
  var x = pick(d.labels);
  plotReact(id, [
    {x: x, y: pick(d.roa), type: 'scatter', mode: 'lines+markers', name: 'ROA(연율화)', connectgaps: true,
     line: {color: '#2980B9', width: 2.5}, hovertemplate: '%{x}<br>ROA %{y:.2f}%<extra></extra>'},
    {x: x, y: pick(d.roa4), type: 'scatter', mode: 'lines+markers', name: 'ROA(4분기누적)', connectgaps: true,
     line: {color: '#85C1E9', width: 2, dash: 'dot'}, visible: roa4Visible,
     hovertemplate: '%{x}<br>ROA(4분기누적) %{y:.2f}%<extra></extra>'},
    {x: x, y: pick(d.rate), type: 'scatter', mode: 'lines+markers', name: '기준금리(우축·역축)', yaxis: 'y2',
     line: {color: '#E67E73', width: 2.5, shape: 'hv'}, hovertemplate: '%{x}<br>기준금리 %{y:.2f}%<extra></extra>'}
  ], {
    height: 440, margin: {t: 30, b: 80, l: 60, r: 60},
    xaxis: {type: 'category', tickangle: -45},
    yaxis: {title: 'ROA (%)', zeroline: true, zerolinecolor: '#999'},
    yaxis2: {title: '기준금리 (%)', overlaying: 'y', side: 'right', autorange: 'reversed', showgrid: false},
    legend: {orientation: 'h', y: -0.3}
  }, {displaylogo: false, responsive: true});
}

"""


def build() -> str:
    sectors = list(SECTOR_FOLDERS.keys())
    page_keys = {s: f"sector{i}" for i, s in enumerate(sectors)}

    nav_links = "".join(
        f'<a href="#{page_keys[s]}" id="nav-{page_keys[s]}" onclick="showPage(\'{page_keys[s]}\');return false;">'
        f'<span>{s}</span></a>'
        for s in sectors
    )

    page_divs = []
    for s in sectors:
        print(f"  - {s} 생성 중...", flush=True)
        key = page_keys[s]
        content = render_savings_bank_page(key, s) if s == "상호저축은행" else render_sector(s)
        page_divs.append(f'<div class="page" id="page-{key}"><h1>{s}</h1>{content}</div>')

    generated_at = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    cr_metrics_js = json.dumps(CR_METRICS, ensure_ascii=False)
    kis_js = (Path(__file__).resolve().parent / "kis_charts.js").read_text(encoding="utf-8")
    js = f'var DEFAULT_PAGE = "{page_keys[sectors[0]]}";\nvar CR_METRICS_JS = {cr_metrics_js};\n' + JS + kis_js

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FISIS 업권별 실적 대시보드</title>
<script src="https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2/plotly.min.js"></script>
<script>{js}</script>
<style>{CSS}</style>
</head>
<body>
<div id="layout">
  <nav id="sidebar">
    <div class="brand">FISIS 업권별 실적</div>
    {nav_links}
  </nav>
  <main id="main">
    <div id="top-note">최종 갱신: {generated_at} (매일 자동 갱신)</div>
    {''.join(page_divs)}
  </main>
</div>
</body>
</html>"""


def main():
    out_dir = REPO_DIR / "docs"
    out_dir.mkdir(exist_ok=True)

    print("정적 사이트 생성 시작...")
    html = build()
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    size_mb = len(html.encode("utf-8")) / 1024 / 1024
    print(f"완료: {out_dir / 'index.html'} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
