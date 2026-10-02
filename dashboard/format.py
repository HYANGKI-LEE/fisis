import pandas as pd


def format_eok(value):
    if pd.isna(value):
        return "-"
    return f"{value / 1e8:,.0f}억원"


def format_pct(value):
    if pd.isna(value):
        return "-"
    return f"{value:.2f}%"


def format_ym(ym):
    if pd.isna(ym):
        return "-"
    ym = int(ym)
    year, month = ym // 100, ym % 100
    quarter = (month - 1) // 3 + 1
    return f"{year}.Q{quarter}"


def latest_snapshot(kpi: pd.DataFrame) -> pd.DataFrame:
    """회사별로 지표마다 가장 최근 값을 독립적으로 골라 스냅샷 테이블 구성."""
    rows = []
    for company, g in kpi.groupby("금융회사명"):
        g = g.sort_values("년월")
        ni_row = g.dropna(subset=["당기순이익"]).tail(1)
        roa_row = g.dropna(subset=["ROA"]).tail(1)
        roe_row = g.dropna(subset=["ROE"]).tail(1)
        rows.append(
            {
                "금융회사명": company,
                "기준분기": ni_row["년월"].iloc[0] if len(ni_row) else pd.NA,
                "당기순이익": ni_row["당기순이익"].iloc[0] if len(ni_row) else pd.NA,
                "전기대비증감률": ni_row["당기순이익_전기대비증감률"].iloc[0] if len(ni_row) else pd.NA,
                "ROA": roa_row["ROA"].iloc[0] if len(roa_row) else pd.NA,
                "ROE": roe_row["ROE"].iloc[0] if len(roe_row) else pd.NA,
            }
        )
    return pd.DataFrame(rows).sort_values("당기순이익", ascending=False)


SNAPSHOT_FULL_METRICS = [
    "영업수익", "영업이익", "영업이익률", "영업이익_전년대비증감률",
    "당기순이익", "당기순이익률", "당기순이익_전년대비증감률", "ROA", "ROE",
]


def latest_snapshot_full(kpi: pd.DataFrame) -> pd.DataFrame:
    """latest_snapshot보다 넓은 지표 세트(영업수익/영업이익 등 포함) 버전."""
    rows = []
    for company, g in kpi.groupby("금융회사명"):
        g = g.sort_values("년월")
        row = {"금융회사명": company}
        ni_row = g.dropna(subset=["당기순이익"]).tail(1)
        row["기준분기"] = ni_row["년월"].iloc[0] if len(ni_row) else pd.NA
        for metric in SNAPSHOT_FULL_METRICS:
            m_row = g.dropna(subset=[metric]).tail(1)
            row[metric] = m_row[metric].iloc[0] if len(m_row) else pd.NA
        rows.append(row)
    return pd.DataFrame(rows).sort_values("당기순이익", ascending=False).reset_index(drop=True)
