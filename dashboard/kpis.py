import pandas as pd

# 항목(당분기/누계 등) 중 우선순위 - 분기 단독 값을 우선 사용
ITEM_PRIORITY = ["당분기", "금액"]


def _pick_by_item_priority(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """(회사, 년월, 통계표명, 구분) 그룹 내에 항목이 여러 개면 우선순위대로 하나만 선택."""
    if "항목" not in df.columns or df["항목"].notna().sum() == 0:
        return df

    def rank(item):
        if pd.isna(item):
            return len(ITEM_PRIORITY)
        return ITEM_PRIORITY.index(item) if item in ITEM_PRIORITY else len(ITEM_PRIORITY) - 1

    df = df.copy()
    df["_rank"] = df["항목"].map(rank)
    df = df.sort_values("_rank").drop_duplicates(subset=group_cols, keep="first")
    return df.drop(columns="_rank")


def extract_net_income(long_df: pd.DataFrame) -> pd.DataFrame:
    """요약손익계산서류 표에서 당기순이익(개별 기준)만 추출."""
    is_income_tbl = long_df["통계표명"].str.startswith("요약손익계산서", na=False)
    gubun = long_df["구분"].astype(str)
    is_net_income = (
        gubun.str.contains("당기순이익", regex=False)
        & ~gubun.str.contains("_", regex=False)
        & ~gubun.str.contains("대손", regex=False)
        & ~gubun.str.contains("주당", regex=False)
    )
    sub = long_df[is_income_tbl & is_net_income]
    sub = _pick_by_item_priority(sub, ["금융회사명", "년월", "통계표명", "구분"])
    out = sub.groupby(["금융회사명", "년월"], as_index=False)["값"].sum()
    return out.rename(columns={"값": "당기순이익"})


def extract_ratio(long_df: pd.DataFrame, keywords: list[str]) -> pd.DataFrame:
    """수익성/경영효율지표류 표에서 특정 비율 지표(ROA, ROE 등) 추출."""
    is_ratio_tbl = long_df["통계표명"].str.startswith("수익성", na=False) | (
        long_df["통계표명"] == "경영효율지표"
    )
    gubun = long_df["구분"].astype(str)
    mask = pd.Series(False, index=long_df.index)
    for kw in keywords:
        mask |= gubun.str.contains(kw, regex=False)
    sub = long_df[is_ratio_tbl & mask]
    sub = sub.drop_duplicates(subset=["금융회사명", "년월"], keep="first")
    out = sub[["금융회사명", "년월", "값"]].copy()

    # [경영효율지표] 총자산순이익률: 2023.1Q(IFRS17 전환) 이후 전 보험사가 예외 없이
    # 정확히 50.0으로 찍히는 FISIS 원본 데이터 이상 - 실제 값이 아니므로 결측 처리
    out.loc[out["값"] == 50.0, "값"] = pd.NA
    return out


def build_kpi_table(long_df: pd.DataFrame) -> pd.DataFrame:
    """회사 x 년월 단위의 핵심 수익지표 테이블 생성."""
    net_income = extract_net_income(long_df)
    roa = extract_ratio(long_df, ["총자산순이익률", "총자산이익율"]).rename(columns={"값": "ROA"})
    roe = extract_ratio(
        long_df, ["자기자본순이익률", "자기자본이익률", "자기자본이익율"]
    ).rename(columns={"값": "ROE"})

    out = net_income.merge(roa, on=["금융회사명", "년월"], how="outer")
    out = out.merge(roe, on=["금융회사명", "년월"], how="outer")
    out = out.sort_values(["금융회사명", "년월"])

    out["당기순이익_전기대비증감률"] = out.groupby("금융회사명")["당기순이익"].pct_change() * 100
    return out
