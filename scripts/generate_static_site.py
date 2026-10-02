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

import pandas as pd
import plotly.express as px

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from dashboard.loader import SECTOR_FOLDERS, load_sector_long  # noqa: E402
from dashboard.kpis import build_kpi_table  # noqa: E402
from dashboard.format import format_eok, format_pct, format_ym, latest_snapshot  # noqa: E402


# FISIS 원본 사이트의 저축은행 통계 분류 체계를 따름 (주요지표는 우리가 만든 요약 탭).
# 내용은 아직 와꾸만 - 자산건전성 이후 11개는 준비중 placeholder.
SAVINGS_BANK_TABS = [
    "주요 지표", "수익성", "자산건전성", "여신건전성", "유동성",
    "자산 현황", "부채 현황", "부문별 손익 현황", "대출금 운용",
    "자본적정성", "대차대조표", "손익계산서",
]

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
def build_sector_js_data(kpi: pd.DataFrame, snap: pd.DataFrame) -> dict:
    """회사 x 분기 전체 시계열을 JSON 구조로 변환 - 서버 없이 드롭다운으로
    회사/분기를 바꿔도 클라이언트에서 바로 차트를 다시 그릴 수 있게."""
    quarters = sorted(kpi["년월"].dropna().unique().tolist())
    quarter_labels = [format_ym(q) for q in quarters]
    companies = snap["금융회사명"].tolist()  # 이미 당기순이익 내림차순 정렬됨

    series = {}
    for company in companies:
        g = (kpi[kpi["금융회사명"] == company]
             .drop_duplicates(subset="년월")
             .set_index("년월")
             .reindex(quarters))
        series[company] = {
            metric: [None if pd.isna(v) else float(v) for v in g[metric]]
            for metric in ("당기순이익", "ROA", "ROE")
        }

    return {"quarters": quarter_labels, "companies": companies, "series": series}


def render_main_tab_rich(sector_key: str, kpi: pd.DataFrame, snap: pd.DataFrame) -> str:
    display = snap.copy()
    display["기준분기"] = display["기준분기"].map(format_ym)
    display["당기순이익"] = display["당기순이익"].map(format_eok)
    display["전기대비증감률"] = display["전기대비증감률"].map(format_pct)
    display["ROA"] = display["ROA"].map(format_pct)
    display["ROE"] = display["ROE"].map(format_pct)
    table_html = df_to_html(display)

    js_data = build_sector_js_data(kpi, snap)
    data_script = (f'<script type="application/json" id="data-{sector_key}">'
                    f'{json.dumps(js_data, ensure_ascii=False, separators=(",", ":"))}</script>')

    quarter_options = "".join(
        f'<option value="{q}"{" selected" if i == len(js_data["quarters"]) - 1 else ""}>{q}</option>'
        for i, q in enumerate(js_data["quarters"])
    )
    company_options = "".join(f"<option value=\"{c}\">" for c in js_data["companies"])
    default_company = js_data["companies"][0] if js_data["companies"] else ""

    bar_section = (
        '<h4>회사별 실적 비교</h4>'
        '<div class="control-row"><label>기준 분기 '
        f'<select id="quarterSelect-{sector_key}" onchange="onQuarterChange(\'{sector_key}\')">'
        f'{quarter_options}</select></label></div>'
        f'<div id="barChart-{sector_key}" class="plotly-chart"></div>'
    )

    trend_section = (
        '<h4>회사별 추이</h4>'
        '<div class="control-row"><label>회사 선택(검색 가능) '
        f'<input type="text" id="companySelect-{sector_key}" list="companyList-{sector_key}" '
        f'value="{default_company}" oninput="onCompanyChange(\'{sector_key}\')"></label>'
        f'<datalist id="companyList-{sector_key}">{company_options}</datalist></div>'
        f'<div class="grid" style="grid-template-columns:1fr 1fr;">'
        f'<div class="cell"><div id="trendNI-{sector_key}" class="plotly-chart"></div></div>'
        f'<div class="cell"><div id="trendRoaRoe-{sector_key}" class="plotly-chart"></div></div>'
        f'</div>'
    )

    return (
        data_script + bar_section + trend_section +
        f'<h4>회사별 최신 실적</h4>{table_html}'
        f'<script>initSectorMain("{sector_key}");</script>'
    )


def render_placeholder_tab(label: str) -> str:
    return f'<p class="caption">"{label}" 탭은 준비 중이에요. 곧 채워질 예정입니다.</p>'


def render_savings_bank_page(sector_key: str, sector: str) -> str:
    long_df = load_sector_long(sector)
    kpi = build_kpi_table(long_df)
    if kpi.empty or kpi["당기순이익"].dropna().empty:
        main_content = '<p class="caption">아직 수집된 데이터가 없어요.</p>'
    else:
        snap = latest_snapshot(kpi)
        main_content = render_main_tab_rich(sector_key, kpi, snap)

    bodies = [main_content] + [render_placeholder_tab(lbl) for lbl in SAVINGS_BANK_TABS[1:]]
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
#main { flex:1; min-width:0; padding:24px 32px 60px; }
#main h1 { font-size:28px; margin:0 0 6px; }
#top-note { color:var(--muted); font-size:13px; margin-bottom:18px; }
.page { display:none; }
.page.active { display:block; }
.grid { display:grid; gap:16px; margin:10px 0; }
.cell { min-width:0; }
.plotly-chart { width:100%; }
.caption { color:var(--muted); font-size:13px; margin:4px 0 10px; }
.caption a { color:var(--accent); }
.data-table { width:100%; border-collapse:collapse; font-size:14px; margin:10px 0; }
.data-table th { text-align:right; padding:6px 8px; border-bottom:2px solid #333; }
.data-table th:first-child, .data-table td:first-child { text-align:left; }
.data-table td { text-align:right; padding:5px 8px; border-bottom:1px solid #eee; }
.tabgroup { margin-top:8px; }
.tab-bar { display:flex; gap:4px; border-bottom:2px solid var(--border); margin-bottom:16px;
           overflow-x:auto; flex-wrap:nowrap; }
.tab-btn { border:none; background:none; padding:10px 14px; font-size:14px; cursor:pointer; color:var(--muted);
           border-bottom:2px solid transparent; margin-bottom:-2px; white-space:nowrap; }
.tab-btn:hover { color:var(--text); }
.tab-btn.active { color:var(--accent); border-bottom-color:var(--accent); font-weight:600; }
.tab-panel { display:none; }
.tab-panel.active { display:block; }
.control-row { margin:10px 0 16px; font-size:14px; }
.control-row label { display:flex; align-items:center; gap:8px; }
.control-row select, .control-row input { border:1px solid var(--border); border-radius:6px; padding:6px 10px;
                                           font-size:14px; min-width:220px; }
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
  setTimeout(function(){ resizeCharts(page.querySelector('.tab-panel.active') || page); }, 0);
}
function showTab(groupId, idx) {
  var group = document.querySelector('[data-group="' + groupId + '"]');
  var btns = group.querySelectorAll('.tab-btn');
  var panels = group.querySelectorAll('.tab-panel');
  btns.forEach(function(b, i){ b.classList.toggle('active', i === idx); });
  panels.forEach(function(p, i){ p.classList.toggle('active', i === idx); });
  setTimeout(function(){ resizeCharts(panels[idx]); }, 0);
}
function renderChart(id) {
  var payload = JSON.parse(document.getElementById(id + '-data').textContent);
  Plotly.newPlot(id, payload.data, payload.layout, {displaylogo:false, responsive:true});
}

var SECTOR_DATA = {};
function initSectorMain(sector) {
  var el = document.getElementById('data-' + sector);
  if (!el) return;
  SECTOR_DATA[sector] = JSON.parse(el.textContent);
  renderBarChart(sector);
  renderTrendCharts(sector);
}
function onQuarterChange(sector) { renderBarChart(sector); }
function onCompanyChange(sector) { renderTrendCharts(sector); }

function renderBarChart(sector) {
  var data = SECTOR_DATA[sector];
  if (!data) return;
  var q = document.getElementById('quarterSelect-' + sector).value;
  var qIdx = data.quarters.indexOf(q);
  var pairs = data.companies
    .map(function(c){ return [c, data.series[c]['당기순이익'][qIdx]]; })
    .filter(function(p){ return p[1] !== null && p[1] !== undefined; });
  pairs.sort(function(a, b){ return b[1] - a[1]; });
  var x = pairs.map(function(p){ return p[0]; });
  var y = pairs.map(function(p){ return p[1]; });
  Plotly.react('barChart-' + sector, [{x:x, y:y, type:'bar', marker:{color:'#2980B9'}}], {
    height:420, margin:{t:20, b:140}, xaxis:{tickangle:-45}, yaxis:{title:'당기순이익(원)'}
  }, {displaylogo:false, responsive:true});
}

function renderTrendCharts(sector) {
  var data = SECTOR_DATA[sector];
  if (!data) return;
  var company = document.getElementById('companySelect-' + sector).value;
  if (data.companies.indexOf(company) === -1) return;
  var s = data.series[company];
  Plotly.react('trendNI-' + sector, [{x:data.quarters, y:s['당기순이익'], type:'bar', marker:{color:'#2980B9'}}], {
    height:360, margin:{t:40}, title:company + ' 당기순이익 추이', yaxis:{title:'당기순이익(원)'}
  }, {displaylogo:false, responsive:true});

  var traces = [];
  if (s['ROA'].some(function(v){ return v !== null; }))
    traces.push({x:data.quarters, y:s['ROA'], mode:'lines+markers', name:'ROA'});
  if (s['ROE'].some(function(v){ return v !== null; }))
    traces.push({x:data.quarters, y:s['ROE'], mode:'lines+markers', name:'ROE'});
  Plotly.react('trendRoaRoe-' + sector, traces, {
    height:360, margin:{t:40}, title:company + ' ROA / ROE 추이', yaxis:{title:'%'}
  }, {displaylogo:false, responsive:true});
}

document.addEventListener('DOMContentLoaded', function() {
  var hash = location.hash.replace('#', '');
  var valid = document.getElementById('page-' + hash);
  showPage(valid ? hash : DEFAULT_PAGE);
});
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
    js = f'var DEFAULT_PAGE = "{page_keys[sectors[0]]}";\n' + JS

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
