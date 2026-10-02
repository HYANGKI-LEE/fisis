"""app.py(Streamlit)를 GitHub Pages용 정적 HTML(docs/index.html)로 내보낸다.

TradingCheckboard(../TradingCheckboard/scripts/generate_static_site.py)와 같은
방식: 업권별 "페이지"를 사이드바로 전환하고, Plotly 차트는 JSON으로 그대로
내장해서 브라우저에서 바로 렌더링한다(서버 없이 정적 파일만으로 동작).

라이브 앱(Streamlit)과의 차이: 회사 선택 드롭다운은 당기순이익 1위 회사만
기본으로 보여준다 - 업권마다 회사가 수십~백여 개라 전부 차트로 구워 넣으면
파일이 너무 커짐. 다른 회사를 보고 싶으면 라이브 앱 링크를 안내한다.
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from dashboard.loader import SECTOR_FOLDERS, load_sector_long  # noqa: E402
from dashboard.kpis import build_kpi_table  # noqa: E402
from dashboard.format import format_eok, format_pct, format_ym, latest_snapshot  # noqa: E402

LIVE_APP_URL = "https://fisis-dashboard.streamlit.app"

_chart_counter = [0]


def chart_div(fig) -> str:
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

    note = (f'<p class="caption">회사별 최신 실적(당기순이익 1위 기준 추이 차트)만 보여줘요. '
            f'다른 회사를 선택해서 보려면 <a href="{LIVE_APP_URL}" target="_blank">라이브 앱</a>을 이용하세요.</p>')

    return (
        f'<h4>회사별 최신 실적</h4>{table_html}'
        f'{note}'
        f'<div class="grid" style="grid-template-columns:1fr 1fr;">'
        f'<div class="cell">{chart_div(fig1)}</div>'
        f'<div class="cell">{chart2_html}</div>'
        f'</div>'
    )


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
  setTimeout(function(){ resizeCharts(page); }, 0);
}
function renderChart(id) {
  var payload = JSON.parse(document.getElementById(id + '-data').textContent);
  Plotly.newPlot(id, payload.data, payload.layout, {displaylogo:false, responsive:true});
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
        content = render_sector(s)
        page_divs.append(
            f'<div class="page" id="page-{page_keys[s]}">'
            f'<h1>{s}</h1>{content}</div>'
        )

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
    <div id="top-note">최종 갱신: {generated_at} (매일 자동 갱신) ·
      <a href="{LIVE_APP_URL}" target="_blank">라이브 앱(회사 선택 가능)</a>으로도 볼 수 있어요.</div>
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
