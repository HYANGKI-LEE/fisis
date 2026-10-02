import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.loader import SECTOR_FOLDERS, load_sector_long
from dashboard.kpis import build_kpi_table
from dashboard.format import format_eok, format_pct, format_ym, latest_snapshot

st.set_page_config(page_title="FISIS 업권별 실적 대시보드", layout="wide")

st.title("FISIS 업권별 실적 대시보드")
st.caption("금융감독원 FISIS 공시데이터 기반 · 핵심 수익지표(당기순이익 / ROA / ROE) 요약")


@st.cache_data
def get_kpi_table(sector: str) -> pd.DataFrame:
    long_df = load_sector_long(sector)
    return build_kpi_table(long_df)


tabs = st.tabs(list(SECTOR_FOLDERS.keys()))

for tab, sector in zip(tabs, SECTOR_FOLDERS.keys()):
    with tab:
        kpi = get_kpi_table(sector)
        if kpi.empty or kpi["당기순이익"].dropna().empty:
            st.info("아직 수집된 데이터가 없어요.")
            continue

        snap = latest_snapshot(kpi)

        display = snap.copy()
        display["기준분기"] = display["기준분기"].map(format_ym)
        display["당기순이익"] = display["당기순이익"].map(format_eok)
        display["전기대비증감률"] = display["전기대비증감률"].map(format_pct)
        display["ROA"] = display["ROA"].map(format_pct)
        display["ROE"] = display["ROE"].map(format_pct)

        st.subheader(f"{sector} · 회사별 최신 실적")
        st.dataframe(display, width="stretch", hide_index=True)

        st.divider()

        companies = snap["금융회사명"].tolist()
        selected = st.selectbox("회사 선택 (추이 보기)", companies, key=f"select_{sector}")

        trend = kpi[kpi["금융회사명"] == selected].sort_values("년월").copy()
        trend["분기"] = trend["년월"].map(format_ym)

        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(trend, x="분기", y="당기순이익", title=f"{selected} 당기순이익 추이")
            fig.update_yaxes(title="당기순이익(원)")
            st.plotly_chart(fig, width="stretch")
        with col2:
            roa_roe = trend.melt(
                id_vars="분기", value_vars=["ROA", "ROE"], var_name="지표", value_name="값"
            ).dropna(subset=["값"])
            if roa_roe.empty:
                st.info("ROA/ROE 데이터가 없어요.")
            else:
                fig2 = px.line(
                    roa_roe, x="분기", y="값", color="지표", markers=True,
                    title=f"{selected} ROA / ROE 추이",
                )
                fig2.update_yaxes(title="%")
                st.plotly_chart(fig2, width="stretch")
