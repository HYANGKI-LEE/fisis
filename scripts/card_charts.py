"""신용카드사 페이지 HTML(탭별 표/차트 자리) 생성. 데이터는 card_data.py, 그리는 건 kis_charts.js(저축은행·증권사와 공용).

하위탭: 주요 지표, 최근 실적, 수익성, 자산건전성, 자본적정성, 유동성, 이용실적, 재무상태표, 손익계산서, 전체 리스트.
항목은 3사(한기평/한신평/NICE) 신용카드 자료의 합집합을 따르되 숫자는 전부 FISIS. 비교선: 카드사 전체(점선, 전업카드사 7개).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kis_charts import PERIOD_PRESETS, _table_html  # noqa: E402
from card_data import ALL_LABEL  # noqa: E402
from sec_charts import _grade_rank  # noqa: E402

TAB_LABELS = ["주요 지표", "최근 실적", "수익성", "자산건전성", "자본적정성", "유동성", "이용실적", "재무상태표", "손익계산서", "전체 리스트"]
COLUMNS = 3
DATA_ID = "kis-data-card"
LIST_ID = "kisCompanyList-card"


def _r(name, unit, key, indent=0, bold=False, fy=None):
    return (name, unit, fy or key, key, indent, bold)


BS_ROWS = [
    _r("현금및예치금", "eok", "bs_cashdep"), _r("유가증권", "eok", "bs_sec"), _r("영업자산", "eok", "bs_ops", 0, True),
    _r("카드자산", "eok", "bs_card", 1), _r("할부금융자산", "eok", "bs_inst", 1), _r("리스자산", "eok", "bs_lease", 1),
    _r("대출채권", "eok", "bs_loan", 1), _r("신기술금융자산", "eok", "bs_nbt", 1), _r("기타자산", "eok", "bs_oth_a"),
    _r("총자산", "eok", "bs_asset", 0, True),
    _r("차입부채", "eok", "bs_borrow"), _r("차입금", "eok", "bs_b_loan", 1), _r("회사채", "eok", "bs_bond", 1),
    _r("영업미지급금", "eok", "bs_pay"), _r("미사용약정충당부채", "eok", "bs_unused"), _r("총부채", "eok", "bs_liab", 0, True),
    _r("자본금", "eok", "bs_capital"), _r("자기자본", "eok", "bs_equity", 0, True),
]

IS_ROWS = [
    ("영업수익", "rev", 0, True), ("카드수익", "r_card", 1, False), ("할부금융수익", "r_inst", 1, False), ("리스수익", "r_lease", 1, False),
    ("대출채권이자수익", "r_loanint", 1, False), ("신기술금융수익", "r_nbt", 1, False), ("유가증권관련수익", "r_sec", 1, False),
    ("기타영업수익", "r_oth", 1, False),
    ("영업비용", "cost", 0, True), ("이자비용", "c_int", 1, False), ("카드비용", "c_card", 1, False), ("할부금융비용", "c_inst", 1, False),
    ("리스비용", "c_lease", 1, False), ("신기술금융비용", "c_nbt", 1, False), ("판매비와관리비", "c_sga", 1, False),
    ("유가증권관련비용", "c_sec", 1, False), ("기타영업비용", "c_oth", 1, False),
    ("충당금적립전영업이익(PPOP)", "ppop", 0, True), ("대손비용", "dae", 0, False), ("대손상각비 등", "dae_gross", 1, False),
    ("대손충당금환입 등", "reversal", 1, False),
    ("영업이익", "op", 0, True), ("당기순이익", "ni", 0, True),
]

NOTE_IS = ("영업수익 = 수익합계 - 대손충당금 환입 등, 영업비용 = 비용합계 - 대손상각비 등, PPOP = 영업수익 - 영업비용, 대손비용 = 대손상각비 등 - 환입 등, "
           "영업이익 = PPOP - 대손비용이에요. FISIS 손익계산서에는 영업외손익 구분이 없어서 영업이익은 법인세비용차감전순이익과 같고, 신평사 자료(영업외손익 분리)와 소폭 달라요.")

TAB_TABLES = {
    "재무상태표": {
        "title": "재무상태표 (단위: 억원)",
        "note": "연도(12월) 열은 해당 연도 12월 말, 4분기 전·당분기 열은 해당 분기 말 값이에요. 영업자산 = 카드자산+할부금융자산+리스자산+대출채권+신기술금융자산이고 "
                "기타자산 = 총자산 - 현금및예치금 - 유가증권 - 영업자산이에요(2011.Q1~, 우리카드 2013.Q2~·하나카드 2014.Q3~). 자료: FISIS(업무보고서).",
        "rows": BS_ROWS,
    },
    "손익계산서": {
        "title": "손익계산서 (단위: 억원)",
        "note": "연도(12월) 열은 해당 연도 4개 분기 합계, 4분기 전·당분기 열은 해당 분기 금액(당분기)이에요. " + NOTE_IS,
        "rows": [(n, "eok", k + "_ltm", k, i, b) for n, k, i, b in IS_ROWS],
    },
    "수익성": {
        "title": "수익성 (단위: 억원, %)",
        "note": "금액은 연초부터 해당 분기까지의 누계예요(연도 12월 열은 연간). 비율은 누계를 연환산하고 총자산은 (직전 결산말+해당 시점) 평균으로 계산했어요: "
                "PPOP/총자산평잔, 대손비용/총자산평잔(대손율), 영업이익/총자산평잔(영업이익률), ROA, ROE. 판관비율 = 판매비와관리비 ÷ 영업수익, 카드수익 비중 = 카드수익 ÷ 영업수익이에요. "
                + NOTE_IS + " 아래 차트는 분기 개별(4분기 누적 포함) 기준이에요.",
        "rows": [
            _r("영업수익", "eok", "is_rev_ytd", 0, True), _r("영업비용", "eok", "is_cost_ytd"), _r("충당금적립전영업이익(PPOP)", "eok", "is_ppop_ytd", 0, True),
            _r("대손비용", "eok", "is_dae_ytd"), _r("영업이익", "eok", "is_op_ytd", 0, True), _r("당기순이익", "eok", "is_ni_ytd", 0, True),
            _r("PPOP/총자산평잔", "pct", "pf_ppop"), _r("대손비용/총자산평잔", "pct", "pf_dae"), _r("영업이익/총자산평잔", "pct", "pf_op"),
            _r("ROA", "pct", "pf_roa"), _r("ROE", "pct", "pf_roe"), _r("판관비/영업수익", "pct", "pf_sga"), _r("카드수익 비중", "pct", "pf_cardshare"),
        ],
    },
    "자산건전성": {
        "title": "자산건전성 (단위: 억원, %)",
        "note": "건전성 분류 총채권·고정이하여신·대손충당금은 FISIS 여신건전성 통계, 연체채권(1개월 이상)은 연체율 통계예요. 고정이하여신비율 = 고정이하여신 ÷ 총채권, "
                "연체채권비율 = 연체채권(1개월 이상) ÷ 총채권, 연체채권비율(대환대출 포함)은 금감원 기준 공시값이에요. 대손충당금/고정이하여신 = 대손충당금(실적립) ÷ 고정이하여신이고, "
                "적립비율(요적립액 대비) = 실적립액 ÷ 요적립액이에요. 요주의 구분은 FISIS에 없어서 요주의이하여신비율은 넣지 못했어요.",
        "rows": [
            _r("건전성 분류 총채권", "eok", "aq_total"), _r("고정이하여신", "eok", "aq_sub"), _r("연체채권(1개월 이상)", "eok", "aq_over"),
            _r("대손충당금 요적립액", "eok", "aq_need"), _r("대손충당금(실적립)", "eok", "aq_allow"),
            _r("고정이하여신비율", "pct", "aq_subr"), _r("연체채권비율(1개월 이상)", "pct", "aq_overr"),
            _r("연체채권비율(대환대출 포함, 금감원 기준)", "pct", "aq_overr2"), _r("대손충당금/고정이하여신", "pct", "aq_cov"),
            _r("대손충당금 적립비율(요적립액 대비)", "pct", "aq_covneed"),
        ],
    },
    "자본적정성": {
        "title": "자본적정성 (단위: 억원, %, 배)",
        "note": "연도(12월) 열은 해당 연도 12월 말, 4분기 전·당분기 열은 해당 분기 말 값이에요. 조정자기자본비율 = 조정자기자본 ÷ 조정총자산(여신전문금융업 감독규정 기준, FISIS 자본적정성 통계), "
                "단순자기자본비율 = 자기자본 ÷ 총자산, 총자산/자기자본 = 레버리지(배)예요. 신평사의 자본완충력배율·조정레버리지는 회사 제시 자료로 조정한 값이라 FISIS에 없어서 넣지 못했어요.",
        "rows": [
            _r("자기자본", "eok", "bs_equity"), _r("총자산", "eok", "bs_asset"), _r("총자산/자기자본 (배)", "x", "bs_lev"),
            _r("조정자기자본", "eok", "cp_adj_cap"), _r("조정총자산", "eok", "cp_adj_asset"),
            _r("조정자기자본비율", "pct", "cp_adjr"), _r("단순자기자본비율", "pct", "cp_simple"),
        ],
    },
    "유동성": {
        "title": "유동성 (단위: 억원, %)",
        "note": "원화 유동성비율 = 원화 유동성자산 ÷ 원화 유동성부채, 즉시가용유동성비율 = 즉시가용유동성자산 ÷ 1개월 이내 만기도래 부채, 단기조달비중 = 단기조달잔액 ÷ 총조달잔액(2022.Q1~)이에요(FISIS 유동성 통계). "
                "자금조달 구성은 FISIS 자금조달현황이고 회사채 조달비중 = 회사채 ÷ 총 자금조달이에요.",
        "rows": [
            _r("원화 유동성자산", "eok", "lq_assets"), _r("원화 유동성부채", "eok", "lq_liab"), _r("원화 유동성비율", "pct", "lq_ratio"),
            _r("즉시가용유동성비율", "pct", "lq_instant"), _r("단기조달비중", "pct", "lq_short"),
        ],
    },
    "이용실적": {
        "title": "카드 이용실적 (단위: 억원, %)",
        "note": "연도(12월) 열은 해당 연도 4개 분기 합계, 4분기 전·당분기 열은 해당 분기 이용실적이에요(FISIS 카드 영업활동, 신용카드는 개인+법인+구매전용 총계). "
                "카드대출 비중 = (현금서비스+카드론) ÷ 신용카드 이용실적, 카드론 비중·할부 비중도 같은 방식이에요.",
        "rows": [
            _r("신용카드 이용실적", "eok", "us_total", 0, True, fy="us_total_ltm"), _r("일시불", "eok", "us_lump", 1, False, fy="us_lump_ltm"),
            _r("할부", "eok", "us_inst", 1, False, fy="us_inst_ltm"), _r("현금서비스", "eok", "us_cash", 1, False, fy="us_cash_ltm"),
            _r("카드론", "eok", "us_loan", 1, False, fy="us_loan_ltm"), _r("개인", "eok", "us_pers", 1, False, fy="us_pers_ltm"),
            _r("법인", "eok", "us_corp", 1, False, fy="us_corp_ltm"), _r("구매전용", "eok", "us_buyonly", 1, False, fy="us_buyonly_ltm"),
            _r("체크카드(직불 포함)", "eok", "us_check", 0, False, fy="us_check_ltm"), _r("선불카드", "eok", "us_prepaid", 0, False, fy="us_prepaid_ltm"),
            _r("카드대출 비중", "pct", "us_loanshare"), _r("카드론 비중", "pct", "us_loanonly"), _r("할부 비중", "pct", "us_instshare"),
        ],
    },
    "주요 지표": {
        "title": "주요 지표 (단위: 억원, %, 배)",
        "note": "연도(12월) 열은 해당 연도 값(손익은 4개 분기 합계), 4분기 전·당분기 열은 해당 분기 값이에요. 비율 정의는 각 하위탭 표 아래 설명을 참고하세요.",
        "rows": [
            _r("총자산", "eok", "bs_asset", 0, True), _r("자기자본", "eok", "bs_equity"),
            _r("영업수익", "eok", "is_rev", 0, False, fy="is_rev_ltm"), _r("충당금적립전영업이익(PPOP)", "eok", "is_ppop", 0, False, fy="is_ppop_ltm"),
            _r("당기순이익", "eok", "is_ni", 0, True, fy="is_ni_ltm"),
            _r("ROA", "pct", "pf_roa"), _r("ROE", "pct", "pf_roe"), _r("PPOP/총자산평잔", "pct", "pf_ppop"),
            _r("고정이하여신비율", "pct", "aq_subr"), _r("연체채권비율(대환대출 포함)", "pct", "aq_overr2"),
            _r("조정자기자본비율", "pct", "cp_adjr"), _r("총자산/자기자본 (배)", "x", "bs_lev"), _r("원화 유동성비율", "pct", "lq_ratio"),
        ],
    },
}

EXTRA_TABLES = {
    "수익성": [{
        "title": "카드수익 구성 (단위: 억원, 누계)",
        "note": "FISIS 손익계산서의 카드수익 세부 항목이에요. 기타 카드수익 = 카드수익 - 위 5개 항목이에요.",
        "rows": [
            _r("카드수익", "eok", "is_r_card_ytd", 0, True), _r("가맹점수수료", "eok", "is_cr_fee_ytd", 1), _r("할부카드수수료", "eok", "is_cr_inst_ytd", 1),
            _r("현금서비스수익", "eok", "is_cr_cash_ytd", 1), _r("카드론수익", "eok", "is_cr_loan_ytd", 1), _r("연회비수익", "eok", "is_cr_annual_ytd", 1),
            _r("기타 카드수익", "eok", "is_cr_oth_ytd", 1),
        ],
    }],
    "유동성": [{
        "title": "자금조달 (단위: 억원, %)",
        "note": "FISIS 자금조달현황(총계)이에요. 유동화자금조달은 자산유동화(ABS) 조달이에요.",
        "rows": [
            _r("총 자금조달", "eok", "fd_total", 0, True), _r("차입금", "eok", "fd_loan", 1), _r("회사채", "eok", "fd_bond", 1),
            _r("유동화자금조달", "eok", "fd_abs", 1), _r("기타", "eok", "fd_other", 1), _r("회사채 조달비중", "pct", "fd_bondr"),
        ],
    }],
}

SECTION_TITLES = {
    "key": "주요 지표 추이 (비교선: 카드사 전체)", "perf_trend": "회사별 추이", "pf": "수익성 추이 (비교선: 카드사 전체)",
    "aq": "자산건전성 (회색 선: 카드사 전체)", "cp": "자본적정성 (회색 선: 카드사 전체)", "lq": "유동성·자금조달 (회색 선: 카드사 전체)",
    "us": "이용실적", "bs": "재무상태표 (단위: 억원)", "is": "손익계산서 (단위: 억원, 당분기)",
}

BLUE, RED, GRAY, ORANGE, GREEN, NAVY, GOLD = "#2980B9", "#E8312F", "#A6A6A6", "#ED7D31", "#70AD47", "#1F3864", "#F5B301"


def _row_charts(rows, parent_names=True):
    out, parent = [], ""
    for name, unit, fy, key, indent, bold in rows:
        if indent == 0:
            parent = name
        title = name if (indent == 0 or not parent_names) else f"{parent} - {name}"
        out.append((key, title, "억원", "bar", None))
    return out


SECTIONS = {
    "key": [
        ("key_roa", "ROA", "%", "cmp3", {"k": "pf_roa"}), ("key_roe", "ROE", "%", "cmp3", {"k": "pf_roe"}),
        ("key_ppop", "PPOP/총자산평잔", "%", "cmp3", {"k": "pf_ppop"}),
        ("key_sub", "고정이하여신비율", "%", "cmp3", {"k": "aq_subr", "gray": True}),
        ("key_over", "연체채권비율(대환대출 포함)", "%", "cmp3", {"k": "aq_overr2", "gray": True}),
        ("key_adj", "조정자기자본비율", "%", "cmp3", {"k": "cp_adjr", "gray": True}),
        ("key_lev", "총자산/자기자본", "배", "cmp3", {"k": "bs_lev", "gray": True}),
        ("key_lq", "원화 유동성비율", "%", "cmp3", {"k": "lq_ratio", "gray": True}),
    ],
    "perf_trend": [
        ("pr_ni", "당기순이익", "억원", "bar", None), ("pr_rev", "영업수익", "억원", "bar", None),
        ("pr_dual", "당기순이익 / ROA", "억원 / %", "dual", {"bar": "is_ni", "line": "pf_roa_q", "bn": "당기순이익", "ln": "ROA(우, 분기 연율화)"}),
        ("pr_ppop", "충당금적립전영업이익(PPOP)", "억원", "bar", None),
        ("pr_roa", "ROA (분기 연율화)", "%", "cmp3", {"k": "pf_roa_q"}), ("pr_roe", "ROE (분기 연율화)", "%", "cmp3", {"k": "pf_roe_q"}),
    ],
    "pf": [
        ("pf_c_rev", "영업수익", "억원", "bar", None), ("pf_c_cost", "영업비용", "억원", "bar", None),
        ("pf_c_ppop", "충당금적립전영업이익(PPOP)", "억원", "bar", None),
        ("pf_c_dae", "대손비용", "억원", "bar", None), ("pf_c_op", "영업이익", "억원", "bar", None), ("pf_c_ni", "당기순이익", "억원", "bar", None),
        ("pf_c_ppopr", "PPOP/총자산평잔 (분기)", "%", "cmp3", {"k": "pf_ppop_q"}), ("pf_c_ppopr4", "PPOP/총자산평잔 (4분기 누적)", "%", "cmp3", {"k": "pf_ppop_4"}),
        ("e_pf1", "", "", "empty", None),
        ("pf_c_daer", "대손비용/총자산평잔 (분기)", "%", "cmp3", {"k": "pf_dae_q"}), ("pf_c_daer4", "대손비용/총자산평잔 (4분기 누적)", "%", "cmp3", {"k": "pf_dae_4"}),
        ("pf_c_opr", "영업이익/총자산평잔 (분기)", "%", "cmp3", {"k": "pf_op_q"}),
        ("pf_c_roa", "ROA (분기 연율화)", "%", "cmp3", {"k": "pf_roa_q"}), ("pf_c_roa4", "ROA (4분기 누적)", "%", "cmp3", {"k": "pf_roa_4"}),
        ("pf_c_roe", "ROE (분기 연율화)", "%", "cmp3", {"k": "pf_roe_q"}),
        ("pf_c_sga", "판관비/영업수익", "%", "cmp3", {"k": "pf_sga"}), ("pf_c_cardsh", "카드수익 비중", "%", "cmp3", {"k": "pf_cardshare"}),
        ("pf_c_cardmix", "카드수익 구성 (분기)", "억원", "stack",
         [("is_cr_fee", "가맹점수수료", BLUE), ("is_cr_inst", "할부카드수수료", RED), ("is_cr_cash", "현금서비스수익", GOLD),
          ("is_cr_loan", "카드론수익", GREEN), ("is_cr_annual", "연회비수익", NAVY), ("is_cr_oth", "기타", GRAY)]),
    ],
    "aq": [
        ("aq_c_sub", "고정이하여신비율", "%", "cmp3", {"k": "aq_subr", "gray": True}),
        ("aq_c_over", "연체채권비율 (1개월 이상)", "%", "cmp3", {"k": "aq_overr", "gray": True}),
        ("aq_c_over2", "연체채권비율 (대환대출 포함)", "%", "cmp3", {"k": "aq_overr2", "gray": True}),
        ("aq_c_cov", "대손충당금/고정이하여신", "%", "cmp3", {"k": "aq_cov", "gray": True}),
        ("aq_c_covneed", "대손충당금 적립비율 (요적립액 대비)", "%", "cmp3", {"k": "aq_covneed", "gray": True}),
    ],
    "cp": [
        ("cp_c_adj", "조정자기자본비율", "%", "cmp3", {"k": "cp_adjr", "gray": True}),
        ("cp_c_simple", "단순자기자본비율", "%", "cmp3", {"k": "cp_simple", "gray": True}),
        ("cp_c_lev", "총자산/자기자본 (레버리지)", "배", "cmp3", {"k": "bs_lev", "gray": True}),
    ],
    "lq": [
        ("lq_c_ratio", "원화 유동성비율", "%", "cmp3", {"k": "lq_ratio", "gray": True}),
        ("lq_c_inst", "즉시가용유동성비율", "%", "cmp3", {"k": "lq_instant", "gray": True}),
        ("lq_c_short", "단기조달비중", "%", "cmp3", {"k": "lq_short", "gray": True}),
        ("fd_c_mix", "자금조달 구성", "억원", "stack",
         [("fd_loan", "차입금", BLUE), ("fd_bond", "회사채", RED), ("fd_abs", "유동화자금조달", GOLD), ("fd_other", "기타", GRAY)]),
        ("fd_c_bondr", "회사채 조달비중", "%", "cmp3", {"k": "fd_bondr", "gray": True}),
    ],
    "us": [
        ("us_c_mix", "신용카드 이용실적 구성 (분기)", "억원", "stack",
         [("us_lump", "일시불", BLUE), ("us_inst", "할부", RED), ("us_cash", "현금서비스", GOLD), ("us_loan", "카드론", GREEN)]),
        ("us_c_total", "신용카드 이용실적 (분기)", "억원", "bar", None),
        ("us_c_check", "체크카드 이용실적 (분기)", "억원", "bar", None),
        ("us_c_loansh", "카드대출 비중", "%", "cmp3", {"k": "us_loanshare", "gray": True}),
        ("us_c_loanonly", "카드론 비중", "%", "cmp3", {"k": "us_loanonly", "gray": True}),
        ("us_c_instsh", "할부 비중", "%", "cmp3", {"k": "us_instshare", "gray": True}),
    ],
    "bs_top": [
        ("bt_asset", "카드사 총자산 구성 추이", "조원", "stackj", {"bars": [
            {"k": "bs_cashdep", "n": "현금및예치금", "c": "#2B2D6E"}, {"k": "bs_sec", "n": "유가증권", "c": "#92C1D6"},
            {"k": "bs_card", "n": "카드자산", "c": "#FFE699"}, {"k": "bs_inst", "n": "할부금융자산", "c": "#6B6EAF"},
            {"k": "bs_lease", "n": "리스자산", "c": "#D9C5B8"}, {"k": "bs_loan_nbt", "n": "대출채권·신기술금융", "c": "#E8B4B0"},
            {"k": "bs_oth_a", "n": "기타자산", "c": "#BFBFBF"}]}),
        ("bt_liab", "카드사 부채·자본 구성 추이", "조원", "stackj", {"bars": [
            {"k": "bs_b_loan", "n": "차입금", "c": "#2B2D6E"}, {"k": "bs_bond", "n": "회사채", "c": "#92C1D6"},
            {"k": "bs_oth_l", "n": "기타부채(차입부채 외)", "c": "#FFE699"}, {"k": "bs_equity", "n": "자기자본", "c": "#6B6EAF"}]}),
        ("e_bt", "", "", "empty", None),
    ],
    "bs": _row_charts(BS_ROWS),
    "is": _row_charts([(n, "eok", k, "is_" + k, i, b) for n, k, i, b in IS_ROWS]),
}
SERIES_KEY = {"pf_c_rev": "is_rev", "pf_c_cost": "is_cost", "pf_c_ppop": "is_ppop", "pf_c_dae": "is_dae", "pf_c_op": "is_op", "pf_c_ni": "is_ni",
              "pr_ni": "is_ni", "pr_rev": "is_rev", "pr_ppop": "is_ppop", "us_c_total": "us_total", "us_c_check": "us_check"}

CHART_NOTES = {
    "bt_asset": "선택 대상의 자산 구성이에요. 대출채권·신기술금융은 두 항목의 합이고, 기타자산 = 총자산 - 나머지 항목이에요.",
    "bt_liab": "차입금 = 차입부채 중 차입금, 회사채 = 사채, 기타부채 = 부채 - 차입부채예요(영업미지급금 등 포함). 부채와 자본 합이 총자산이에요.",
    "pr_dual": "막대: 당기순이익(당분기, 좌축), 선: ROA(우축, 당분기 순이익 ×4 ÷ 총자산 분기 평잔).",
    "pf_c_rev": "차트는 모두 분기 개별 금액이에요(표는 연초부터의 누계). 회사를 고르면 카드사 전체(전업카드사 7개 합산)와 비교하는 비율 차트가 함께 나와요.",
    "pf_c_ppopr": "PPOP/총자산평잔 = 당분기 PPOP ×4 ÷ 총자산 분기 평잔. 4분기 누적은 최근 4개 분기 PPOP ÷ 5개 분기말 평균 총자산이에요.",
    "pf_c_daer": "대손비용/총자산평잔(대손율) = 당분기 대손비용 ×4 ÷ 총자산 분기 평잔.",
    "pf_c_roa": "ROA = 당분기 당기순이익 ×4 ÷ 총자산 분기 평잔. 표의 ROA(누계 연환산)와 값이 달라요.",
    "pf_c_sga": "판관비/영업수익 = 판매비와관리비 ÷ 영업수익(누계).",
    "aq_c_over2": "연체채권비율(1개월 이상, 대환대출 포함)은 금감원 기준 공시값이고, 카드사 전체는 총채권 가중평균이에요.",
    "aq_c_cov": "대손충당금/고정이하여신 = 대손충당금(실적립) ÷ 고정이하여신.",
    "cp_c_adj": "조정자기자본비율 = 조정자기자본 ÷ 조정총자산 (여신전문금융업 감독규정 기준).",
    "lq_c_short": "단기조달비중은 FISIS에 2022.Q1부터 공시돼요.",
    "us_c_mix": "신용카드 이용실적(개인+법인+구매전용) 구성이에요. 체크카드·선불카드는 포함하지 않아요.",
}

# 회사별 비교 막대에서 고를 수 있는 지표
CBAR_KEY = [
    ("pf_roa", "ROA", "%"), ("pf_roe", "ROE", "%"), ("pf_ppop", "PPOP/총자산평잔", "%"), ("aq_subr", "고정이하여신비율", "%"),
    ("aq_overr2", "연체채권비율(대환대출 포함)", "%"), ("cp_adjr", "조정자기자본비율", "%"), ("bs_lev", "총자산/자기자본", "배"),
    ("lq_ratio", "원화 유동성비율", "%"), ("bs_asset", "총자산", "억원"), ("bs_equity", "자기자본", "억원"),
]
CBAR_PERF = [
    ("is_ni", "당기순이익", "억원"), ("is_rev", "영업수익", "억원"), ("is_ppop", "충당금적립전영업이익(PPOP)", "억원"), ("is_op", "영업이익", "억원"),
    ("pf_roa", "ROA", "%"), ("pf_roe", "ROE", "%"),
]
CTABLE_COLS = [
    {"n": "영업수익", "k": "is_rev", "u": "eok"}, {"n": "PPOP", "k": "is_ppop", "u": "eok"}, {"n": "영업이익", "k": "is_op", "u": "eok"},
    {"n": "당기순이익", "k": "is_ni", "u": "eok"}, {"n": "당기순이익 전년동기대비", "k": "is_ni", "u": "pct", "yoy": True},
    {"n": "ROA", "k": "pf_roa", "u": "pct"}, {"n": "ROE", "k": "pf_roe", "u": "pct"}, {"n": "총자산", "k": "bs_asset", "u": "eok"},
]

# 3사 신용등급(2026.06): 한기평 Data Sheet / 한신평 Data Package 표지. NICE NDB에는 등급이 없어 비워둠.
RATINGS = {
    "신한카드": ("AA+(S)", "AA+/S", None), "삼성카드": ("AA+(S)", "AA+/S", None), "KB국민카드": ("AA+(S)", "AA+/S", None),
    "현대카드": ("AA+(S)", "AA+/S", None), "롯데카드": ("AA-(S)", "AA-/S", None), "우리카드": ("AA(S)", "AA/S", None),
    "하나카드": ("AA(S)", "AA/S", None), "BC카드": (None, None, None),
}


# ---------------------------------------------------------------- HTML
def render_controls() -> str:
    btns = "".join(
        f'<button data-preset="{p}" onclick="{"kisCustomToggle" if p == "설정" else "kisPreset"}'
        f'({"this" if p == "설정" else f"\'{p}\',this"})">{p}</button>'
        for p in PERIOD_PRESETS
    )
    return (
        '<div class="kis-controls">'
        '<div class="control-row"><label>회사(검색 가능) '
        f'<input type="text" class="kis-company" value="{ALL_LABEL}" list="{LIST_ID}" autocomplete="off" '
        'onfocus="kisCompanyFocus(this)" onblur="kisCompanyBlur(this)" oninput="kisCompanyInput(this)"></label></div>'
        f'<div class="period-bar"><span class="period-label">기간</span>{btns}</div>'
        '<div class="custom-range kis-custom">'
        '<input type="text" class="kis-start" placeholder="2020.Q1" style="width:90px;"> ~ '
        '<input type="text" class="kis-end" placeholder="2026.Q2" style="width:90px;"> '
        '<button onclick="kisCustomApply(this)">적용</button></div>'
        '</div>'
    )


def _cell(prefix, key, name, unit, kind, extra):
    if kind == "empty":
        return '<div class="cell"></div>'
    attrs = ""
    if kind in ("dual", "cmp3", "cmp3m", "stackj", "scatter"):
        attrs = f" data-{kind}='{json.dumps(extra, ensure_ascii=False)}'"
    elif kind in ("multi", "stack"):
        spec = [{"k": k, "n": n, "c": c} for k, n, c in extra]
        attrs = f" data-{kind}='{json.dumps(spec, ensure_ascii=False)}'"
    series_key = SERIES_KEY.get(key, key)
    note = CHART_NOTES.get(key) or ""
    note_html = f'<p class="caption kis-note">{note}</p>' if note else ""
    return (
        f'<div class="cell"><div class="kis-title">{name} <span>({unit})</span></div>'
        f'<div id="kis-{prefix}-{key}" class="plotly-chart kis-chart" data-key="{series_key}" data-type="{kind}" '
        f'data-name="{name}" data-unit="{unit}" data-share=""{attrs}></div>{note_html}</div>'
    )


def _grid(prefix, items):
    return f'<div class="grid" style="grid-template-columns:repeat({COLUMNS},1fr);">' + "".join(_cell(prefix, *it) for it in items) + "</div>"


def _cbar(prefix, key, title, metrics, quarters):
    opts_m = "".join(f'<option value="{k}">{n}</option>' for k, n, _ in metrics)
    opts_q = "".join(f'<option value="{q}"{" selected" if i == len(quarters) - 1 else ""}>{q}</option>' for i, q in enumerate(quarters))
    spec = [{"k": k, "n": n, "u": u} for k, n, u in metrics]
    return (
        f'<h4>{title}</h4><div class="kis-cbar-box">'
        '<div class="control-row"><label>지표 <select class="kis-cbar-metric" onchange="kisCbarChange(this)">' + opts_m + '</select></label>'
        '<label>기준 분기 <select class="kis-cbar-q" onchange="kisCbarChange(this)">' + opts_q + '</select></label></div>'
        '<div class="grid" style="grid-template-columns:1fr;"><div class="cell">'
        f'<div id="kis-{prefix}-{key}" class="plotly-chart kis-chart" data-key="{key}" data-type="cbar" data-name="{title}" data-unit="" '
        f"data-cbar='{json.dumps(spec, ensure_ascii=False)}'></div>"
        '<p class="caption">선택 기간과 관계없이 고른 기준 분기의 전 회사 값이에요. 빨간 막대는 위에서 고른 회사예요.</p></div></div></div>'
    )


def _ctable(title):
    cols = json.dumps(CTABLE_COLS, ensure_ascii=False)
    return (
        f'<h4>{title} <span class="caption" style="font-weight:normal;">(<span class="kis-ctable-q"></span> 기준 · 선택 기간의 마지막 분기, 열 제목 클릭 시 정렬)</span></h4>'
        f"<div style=\"overflow-x:auto;\"><div class=\"kis-ctable\" data-sort='{{\"c\":4,\"d\":-1}}' data-ctable='{cols}'>"
        '<table class="data-table"><thead></thead><tbody></tbody></table></div></div>'
        '<p class="caption">영업수익·PPOP·영업이익·당기순이익은 해당 분기(당분기) 금액, ROA·ROE는 누계 연환산 기준이에요. BC카드는 카드사 전체 합산에서 빼요.</p>'
    )


def _tables(tab):
    out = []
    if tab in TAB_TABLES:
        out.append(_table_html(TAB_TABLES[tab]))
    for et in EXTRA_TABLES.get(tab, []):
        out.append(_table_html(et))
    return "".join(out)


def render_list_tab(rows: list[dict], qlabel: str) -> str:
    """전체 리스트: FISIS 카드사별 총자산·자기자본·ROA와 3사 신용등급."""
    rows = sorted(rows, key=lambda r: -(r["asset"] or 0))
    body = []
    for i, r in enumerate(rows, 1):
        kr, kis, nice = RATINGS.get(r["name"], (None, None, None))
        cell = lambda v, d: f'<td data-v="{"" if v is None else v}">{d}</td>'
        body.append(
            "<tr>" + cell(i, i) + f'<td data-v="{r["name"]}">{r["name"]}</td>'
            + cell(r["asset"], "" if r["asset"] is None else f'{r["asset"]:,.0f}')
            + cell(r["equity"], "" if r["equity"] is None else f'{r["equity"]:,.0f}')
            + cell(r["roa"], "" if r["roa"] is None else f'{r["roa"]:.2f}%')
            + "".join(f'<td data-v="{_grade_rank(x)}" style="text-align:center;">{x or ""}</td>' for x in (kr, kis, nice))
            + "</tr>"
        )
    heads = ["No", "금융회사명", "총자산(억원)", "자기자본(억원)", "ROA", "한기평(KR)", "한신평", "NICE"]
    th = "".join(
        f'<th class="sortable" data-text="{1 if i == 1 else 0}"{" data-dir=" + chr(34) + "-1" + chr(34) if i == 2 else ""} '
        f'onclick="tblSort(this)">{h}<span class="sort-arrow">{" ▼" if i == 2 else ""}</span></th>'
        for i, h in enumerate(heads))
    return (
        f'<h4>카드사 전체 리스트 <span class="caption" style="font-weight:normal;">(재무는 {qlabel} 기준, 열 제목을 누르면 정렬)</span></h4>'
        f'<div style="overflow-x:auto;"><table class="data-table kis-ltable" id="cardListTable"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
        '<p class="caption">FISIS 신용카드사(전업카드사 7개 + BC카드)예요. 총자산·자기자본·ROA는 FISIS 기준이고 ROA는 당기순이익(누계, 연환산) ÷ ((직전 결산말+해당 시점) 총자산 평균)이에요. '
        '신용등급은 한기평 Data Sheet와 한신평 Data Package의 2026.06 기준 장기등급/전망(S=안정적)이에요. NICE 자료(NDB)에는 신용등급이 없어서 NICE 열은 비어 있고, '
        'BC카드는 한기평·한신평 자료에 없어요.</p>'
    )


def render_bodies(prefix: str, quarters: list[str], list_html: str = "") -> list[str]:
    ctl = render_controls()

    def sec(name):
        return f'<h4>{SECTION_TITLES[name]}</h4>' + _grid(prefix, SECTIONS[name])

    bodies = {
        "주요 지표": ctl + _tables("주요 지표") + _cbar(prefix, "cb_key", "회사별 지표 비교", CBAR_KEY, quarters) + sec("key"),
        "최근 실적": ctl + _cbar(prefix, "cb_perf", "회사별 실적 비교", CBAR_PERF, quarters) + sec("perf_trend") + _ctable("회사별 최신 실적"),
        "수익성": ctl + _tables("수익성") + sec("pf"),
        "자산건전성": ctl + _tables("자산건전성") + sec("aq"),
        "자본적정성": ctl + _tables("자본적정성") + sec("cp"),
        "유동성": ctl + _tables("유동성") + sec("lq"),
        "이용실적": ctl + _tables("이용실적") + sec("us"),
        "재무상태표": (ctl + '<h4>자산·부채 구성 추이 (단위: 조원, 막대 위 숫자는 연말·최신 분기 합계)</h4>' + _grid(prefix, SECTIONS["bs_top"])
                     + _tables("재무상태표") + sec("bs")),
        "손익계산서": ctl + _tables("손익계산서") + sec("is"),
        "전체 리스트": list_html,
    }
    return [bodies[t] for t in TAB_LABELS]


def render_data_script(payload: dict) -> str:
    return (f'<datalist class="kis-datalist" id="{LIST_ID}"></datalist>'
            f'<script type="application/json" class="kis-data" id="{DATA_ID}">'
            f'{json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}</script>')
