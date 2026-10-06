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


def extract_income_line(long_df: pd.DataFrame, keyword: str) -> pd.DataFrame:
    """요약손익계산서류 표에서 특정 손익 항목(당기순이익/영업수익/영업이익 등)만 추출.
    "_"가 붙은 하위항목(예: 당기순이익_(대손준비금...))이나 대손/주당 조정 변형은 제외."""
    is_income_tbl = long_df["통계표명"].str.startswith("요약손익계산서", na=False)
    gubun = long_df["구분"].astype(str)
    is_match = (
        gubun.str.contains(keyword, regex=False)
        & ~gubun.str.contains("_", regex=False)
        & ~gubun.str.contains("대손", regex=False)
        & ~gubun.str.contains("주당", regex=False)
    )
    sub = long_df[is_income_tbl & is_match]
    sub = _pick_by_item_priority(sub, ["금융회사명", "년월", "통계표명", "구분"])
    out = sub.groupby(["금융회사명", "년월"], as_index=False)["값"].sum()
    return out.rename(columns={"값": keyword})


def extract_net_income(long_df: pd.DataFrame) -> pd.DataFrame:
    """요약손익계산서류 표에서 당기순이익(개별 기준)만 추출."""
    return extract_income_line(long_df, "당기순이익")


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


def extract_exact(long_df: pd.DataFrame, table_name: str, gubun_exact: str, out_name: str) -> pd.DataFrame:
    """통계표명/구분을 정확히 지정해서 값 하나를 뽑는 범용 추출기 (연체율, BIS비율,
    자산총계처럼 FISIS 쪽 명칭이 이미 명확한 항목용 - extract_ratio의 fuzzy contains
    매칭과 달리 오매칭 위험이 없음)."""
    sub = long_df[(long_df["통계표명"] == table_name) & (long_df["구분"] == gubun_exact)]
    sub = _pick_by_item_priority(sub, ["금융회사명", "년월", "통계표명", "구분"])
    out = sub[["금융회사명", "년월", "값"]].drop_duplicates(subset=["금융회사명", "년월"])
    return out.rename(columns={"값": out_name})


def _next_quarter(yyyymm) -> int:
    """다음 분기 라벨(YYYYMM) - 전분기말 값을 당분기 행에 붙일 때 사용."""
    y, m = divmod(int(yyyymm), 100)
    m += 3
    if m > 12:
        y, m = y + 1, m - 12
    return y * 100 + m


def build_credit_rating_table(long_df: pd.DataFrame) -> pd.DataFrame:
    """신평사 평가요소표(사업위험/재무위험) 기준 핵심 지표 테이블.

    충당금적립전영업이익률 = (영업이익 + 대손상각비) / 총자산(평잔) * 100 (사용자 확인됨)
    총자산 시장점유율 = 회사 자산총계 / 그 분기 업권 전체 자산총계 합 * 100
    """
    op_income = extract_income_line(long_df, "영업이익")
    daeson = extract_exact(long_df, "요약손익계산서", "기타비용_충당부채전입액_대손상각비", "대손상각비")
    avg_assets = extract_exact(long_df, "수익성", "총자산(평잔)", "총자산평잔")
    total_assets = extract_exact(long_df, "요약재무상태표(자산)", "자산총계", "자산총계")

    overdue_rate = extract_exact(long_df, "자산건전성", "연체율", "연체율")
    substandard_ratio = extract_exact(long_df, "여신건전성", "고정이하여신비율", "고정이하여신비율")
    coverage = extract_exact(long_df, "여신건전성", "대손충당금적립비율(고정이하여신대비)", "고정이하여신Coverage")
    bis_ratio = extract_exact(long_df, "자본적정성(자본적정성지표)", "BIS기준 자기자본비율", "BIS자기자본비율")
    liquidity_ratio = extract_exact(long_df, "유동성", "유동성비율", "유동성비율")

    out = op_income.merge(daeson, on=["금융회사명", "년월"], how="outer")
    out = out.merge(avg_assets, on=["금융회사명", "년월"], how="outer")
    out = out.merge(total_assets, on=["금융회사명", "년월"], how="outer")
    out = out.merge(overdue_rate, on=["금융회사명", "년월"], how="outer")
    out = out.merge(substandard_ratio, on=["금융회사명", "년월"], how="outer")
    out = out.merge(coverage, on=["금융회사명", "년월"], how="outer")
    out = out.merge(bis_ratio, on=["금융회사명", "년월"], how="outer")
    out = out.merge(liquidity_ratio, on=["금융회사명", "년월"], how="outer")

    loan_interest = extract_exact(long_df, "요약손익계산서", "이자수익_대출금이자", "대출이자수익")
    loans = extract_exact(long_df, "요약재무상태표(자산)", "대출채권", "대출채권")
    out = out.merge(loan_interest, on=["금융회사명", "년월"], how="outer")
    out = out.merge(loans, on=["금융회사명", "년월"], how="outer")
    out = out.sort_values(["금융회사명", "년월"]).reset_index(drop=True)

    # 대출이자수익률 = 연환산(x4) 당분기 대출금이자수익 / 대출채권 분기 평잔 (당분기말과 직전 분기말 평균)
    prev = out[["금융회사명", "년월", "대출채권"]].copy()
    prev["년월"] = prev["년월"].map(_next_quarter)
    prev = prev.rename(columns={"대출채권": "전분기말대출채권"})
    out = out.merge(prev, on=["금융회사명", "년월"], how="left")
    avg_loans = (out["대출채권"] + out["전분기말대출채권"]) / 2
    out["대출이자수익률"] = out["대출이자수익"] * 4 / avg_loans * 100
    out = out.drop(columns=["전분기말대출채권"])

    out["충당금적립전영업이익률"] = (out["영업이익"] + out["대손상각비"]) / out["총자산평잔"] * 100

    industry_total = out.groupby("년월")["자산총계"].transform("sum")
    out["총자산시장점유율"] = out["자산총계"] / industry_total * 100

    return out


def _yoy_growth(df: pd.DataFrame, value_col: str) -> pd.Series:
    """전년동기대비 증감률(%) - 년월은 YYYYMM이라 "1년 전 같은 분기"는 그냥 -100."""
    prior = df[["금융회사명", "년월", value_col]].copy()
    prior["년월"] = prior["년월"] + 100
    prior = prior.rename(columns={value_col: "_prior"})
    merged = df.merge(prior, on=["금융회사명", "년월"], how="left")
    growth = (merged[value_col] - merged["_prior"]) / merged["_prior"].abs() * 100
    return growth.replace([float("inf"), float("-inf")], pd.NA).values


def build_kpi_table(long_df: pd.DataFrame) -> pd.DataFrame:
    """회사 x 년월 단위의 핵심 수익지표 테이블 생성."""
    net_income = extract_net_income(long_df)
    op_revenue = extract_income_line(long_df, "영업수익")
    op_income = extract_income_line(long_df, "영업이익")
    roa = extract_ratio(long_df, ["총자산순이익률", "총자산이익율"]).rename(columns={"값": "ROA"})
    roe = extract_ratio(
        long_df, ["자기자본순이익률", "자기자본이익률", "자기자본이익율"]
    ).rename(columns={"값": "ROE"})

    out = net_income.merge(op_revenue, on=["금융회사명", "년월"], how="outer")
    out = out.merge(op_income, on=["금융회사명", "년월"], how="outer")
    out = out.merge(roa, on=["금융회사명", "년월"], how="outer")
    out = out.merge(roe, on=["금융회사명", "년월"], how="outer")
    out = out.sort_values(["금융회사명", "년월"]).reset_index(drop=True)

    out["영업이익률"] = out["영업이익"] / out["영업수익"] * 100
    out["당기순이익률"] = out["당기순이익"] / out["영업수익"] * 100

    out["당기순이익_전기대비증감률"] = out.groupby("금융회사명")["당기순이익"].pct_change() * 100
    out["영업이익_전년대비증감률"] = _yoy_growth(out, "영업이익")
    out["당기순이익_전년대비증감률"] = _yoy_growth(out, "당기순이익")
    return out
