"""부동산신탁 페이지 HTML(탭별 표/차트 자리) 생성. 데이터는 trust_data.py, 그리는 건 kis_charts.js(저축은행·증권사·카드사와 공용).

하위탭: 주요 지표, 최근 실적, 수익성, 자산건전성, 자본적정성, 유동성, 수수료수익, 재무상태표, 손익계산서, 전체 리스트.
항목은 신평사(한기평/NICE) 부동산신탁 자료의 합집합을 따르되 숫자는 전부 FISIS. 비교선: 부동산신탁 전체(점선, FISIS 14개사 합산).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kis_charts import PERIOD_PRESETS, _table_html  # noqa: E402
from trust_data import ALL_LABEL  # noqa: E402
from sec_charts import _grade_rank  # noqa: E402

TAB_LABELS = ["주요 지표", "최근 실적", "수익성", "자산건전성", "자본적정성", "유동성", "수수료수익", "재무상태표", "손익계산서", "전체 리스트"]
COLUMNS = 3
DATA_ID = "kis-data-trust"
LIST_ID = "kisCompanyList-trust"


def _r(name, unit, key, indent=0, bold=False, fy=None):
    return (name, unit, fy or key, key, indent, bold)


BS_ROWS = [
    _r("현금및예치금", "eok", "bs_cashdep"), _r("유가증권", "eok", "bs_sec"), _r("대출채권(대손충당금 차감)", "eok", "bs_loan"),
    _r("신탁계정대(총액)", "eok", "bs_tl", 1), _r("신탁계정대 대손충당금", "eok", "bs_tl_allow", 1), _r("신탁계정대(장부가액)", "eok", "bs_tl_net", 1),
    _r("유형자산", "eok", "bs_tang"), _r("기타자산", "eok", "bs_oth_a"), _r("총자산", "eok", "bs_asset", 0, True),
    _r("차입부채", "eok", "bs_borrow"), _r("차입금", "eok", "bs_b_loan", 1), _r("사채", "eok", "bs_bond", 1),
    _r("기타부채", "eok", "bs_oth_l"), _r("총부채", "eok", "bs_liab", 0, True),
    _r("자본금", "eok", "bs_capital"), _r("자기자본", "eok", "bs_equity", 0, True),
    _r("대손충당금 합계(대출채권+기타자산)", "eok", "bs_allow_tot"),
]

IS_ROWS = [
    ("영업수익", "rev", 0, True), ("수수료수익", "r_fee", 1, False), ("증권평가 및 처분이익", "r_sec", 1, False), ("이자수익", "r_int", 1, False),
    ("기타영업수익", "r_oth", 1, False),
    ("영업비용", "cost", 0, True), ("이자비용", "c_int", 1, False), ("판매비와관리비", "c_sga", 1, False), ("증권평가 및 처분손실", "c_sec", 1, False),
    ("기타영업비용", "c_oth", 1, False),
    ("충당금적립전영업이익(PPOP)", "ppop", 0, True), ("대손비용", "dae", 0, False), ("대손상각비 등", "dae_gross", 1, False),
    ("대손충당금환입 등", "reversal", 1, False), ("기타충당금적립", "provoth", 0, False),
    ("영업이익", "op", 0, True), ("영업외손익", "nonop", 0, False), ("법인세차감전순이익", "pretax", 0, False), ("당기순이익", "ni", 0, True),
    ("대손준비금전입액", "reserve", 0, False), ("대손준비금반영후조정이익", "adjni", 0, False),
]

NOTE_IS = ("영업수익 = FISIS 영업수익 - 충당금 환입(충당금환입액·기타대손충당금환입·대출채권 대손충당금환입), 영업비용 = FISIS 영업비용 - 대손상각비 등(대출채권 관련 손실+기타대손상각비) - 충당금전입액, "
           "PPOP = 영업수익 - 영업비용, 대손비용 = 대손상각비 등 - 대손충당금 환입, 기타충당금적립 = 충당금전입액 - 충당금환입액, 영업이익 = PPOP - 대손비용 - 기타충당금적립이에요(FISIS 영업이익과 같아요). "
           "대손준비금전입액은 당기순이익에서 적립한 대손준비금이고, 대손준비금반영후조정이익 = 당기순이익 - 대손준비금전입액이에요.")

TAB_TABLES = {
    "재무상태표": {
        "title": "재무상태표 (단위: 억원)",
        "note": "연도(12월) 열은 해당 연도 12월 말, 4분기 전·당분기 열은 해당 분기 말 값이에요. 신탁계정대·사채·차입금 세부 항목은 FISIS에 2011.Q2부터 있어요. "
                "대손충당금 합계 = 대출채권 대손충당금 + 기타자산 대손충당금이에요(신평사 자료의 '대손충당금(총자산)'). 자료: FISIS(업무보고서).",
        "rows": BS_ROWS,
    },
    "손익계산서": {
        "title": "손익계산서 (단위: 억원)",
        "note": "연도(12월) 열은 해당 연도 4개 분기 합계, 4분기 전·당분기 열은 해당 분기 금액(당분기)이에요. " + NOTE_IS,
        "rows": [(n, "eok", k + "_ltm", k, i, b) for n, k, i, b in IS_ROWS],
    },
    "수익성": {
        "title": "수익성 (단위: 억원, %)",
        "note": "금액은 연초부터 해당 분기까지의 누계예요(연도 12월 열은 연간). 비율은 누계를 연환산하고 총자산·자기자본은 (직전 결산말+해당 시점) 평균으로 계산했어요(한기평 방식): "
                "PPOP/총자산평잔, 대손비용/총자산평잔(대손율), 영업이익/총자산평잔, ROA, ROE. 영업순이익률 = 당기순이익 ÷ 영업수익, 판관비/영업수익 = 판매비와관리비 ÷ 영업수익, "
                "판관비용률 = 판매비와관리비(연환산) ÷ 총자산평잔이에요. 토지신탁수익비중 = (토지신탁 수수료수익 + 신탁계정대 이자수익) ÷ FISIS 영업수익(충당금환입 포함)이고(NICE 방식), "
                "영업수익 점유율은 FISIS 14개사 영업수익 합계 대비 비중이에요. " + NOTE_IS + " 아래 차트는 분기 개별(4분기 누적 포함) 기준이에요.",
        "rows": [
            _r("영업수익", "eok", "is_rev_ytd", 0, True), _r("영업비용", "eok", "is_cost_ytd"), _r("충당금적립전영업이익(PPOP)", "eok", "is_ppop_ytd", 0, True),
            _r("대손비용", "eok", "is_dae_ytd"), _r("기타충당금적립", "eok", "is_provoth_ytd"), _r("영업이익", "eok", "is_op_ytd", 0, True),
            _r("당기순이익", "eok", "is_ni_ytd", 0, True), _r("대손준비금전입액", "eok", "is_reserve_ytd"), _r("대손준비금반영후조정이익", "eok", "is_adjni_ytd"),
            _r("PPOP/총자산평잔", "pct", "pf_ppop"), _r("대손비용/총자산평잔", "pct", "pf_dae"), _r("영업이익/총자산평잔", "pct", "pf_op"),
            _r("ROA", "pct", "pf_roa"), _r("ROE", "pct", "pf_roe"), _r("영업순이익률", "pct", "pf_nim"), _r("판관비/영업수익", "pct", "pf_sga"),
            _r("판관비용률", "pct", "pf_sgaa"), _r("토지신탁수익비중", "pct", "pf_landsh"), _r("영업수익 점유율", "pct", "ms_rev"),
        ],
    },
    "자산건전성": {
        "title": "자산건전성 (단위: 억원, %)",
        "note": "자산건전성 분류(FISIS) 합계 기준이에요. 분류대상 자산 = 대여금·매입대출채권·신탁계정대·미수금·미수수익 등, 고정이하 = 고정+회수의문+추정손실, 요주의이하 = 요주의+고정이하예요. "
                "(충당금+자기자본)/요주의이하자산 = (대출채권 대손충당금+기타자산 대손충당금+자기자본) ÷ 요주의이하자산, 자기자본 대비 순고정이하자산비율 = (고정이하자산-대손충당금) ÷ 자기자본, "
                "신탁계정대충당금/신탁계정대 = 신탁계정대 대손충당금 ÷ 신탁계정대(총액), 신탁계정대(순)/자기자본 = (신탁계정대-충당금) ÷ 자기자본이에요. 신탁계정대 세부 항목은 2011.Q2부터 있어요.",
        "rows": [
            _r("분류대상 자산", "eok", "aq_total"), _r("정상", "eok", "aq_normal", 1), _r("요주의", "eok", "aq_watch", 1), _r("고정", "eok", "aq_fix", 1),
            _r("회수의문", "eok", "aq_doubt", 1), _r("추정손실", "eok", "aq_loss", 1), _r("고정이하자산", "eok", "aq_sub", 0, True), _r("요주의이하자산", "eok", "aq_watchup", 0, True),
            _r("대손충당금 합계", "eok", "bs_allow_tot"), _r("신탁계정대(총액)", "eok", "bs_tl"), _r("신탁계정대 대손충당금", "eok", "bs_tl_allow"),
            _r("요주의이하자산비중", "pct", "aq_watchr"), _r("고정이하자산비중", "pct", "aq_subr"), _r("(충당금+자기자본)/요주의이하자산", "pct", "aq_cov"),
            _r("자기자본 대비 순고정이하자산비율", "pct", "aq_netsub"), _r("신탁계정대충당금/신탁계정대", "pct", "aq_tl_ar"),
            _r("신탁계정대(순)/자기자본", "pct", "aq_tl_eq"), _r("신탁계정대 고정이하 비중", "pct", "aq_tl_subr"),
        ],
    },
    "자본적정성": {
        "title": "자본적정성 (단위: 억원, %, 배)",
        "note": "연도(12월) 열은 해당 연도 12월 말, 4분기 전·당분기 열은 해당 분기 말 값이에요. 영업용순자본비율(NCR) = 영업용순자본 ÷ 총위험액(FISIS 자본적정성 통계, 금융투자업규정)이고 "
                "잉여자본 = 영업용순자본 - 총위험액이에요. 부채비율 = 총부채 ÷ 자기자본, 차입금의존도 = 차입부채 ÷ 총자산, 순차입금의존도 = (차입부채-현금및예치금) ÷ 총자산, "
                "총자산/자기자본 = 레버리지(배)예요. 고정장기적합비율 = 고정자산 ÷ (자기자본+고정부채), 손실위험도가중자산비율 = 손실위험도가중자산 ÷ (자기자본+대손충당금 등)이에요(FISIS 정의).",
        "rows": [
            _r("자기자본", "eok", "bs_equity"), _r("총부채", "eok", "bs_liab"), _r("영업용순자본", "eok", "cp_nc"), _r("총위험액", "eok", "cp_risk"),
            _r("잉여자본", "eok", "cp_surplus", 0, True), _r("영업용순자본비율(NCR)", "pct", "cp_ncr", 0, True), _r("부채비율", "pct", "bs_dr"),
            _r("차입금의존도", "pct", "bs_borrowr"), _r("순차입금의존도", "pct", "bs_netborrowr"), _r("총자산/자기자본 (배)", "x", "bs_lev"),
            _r("고정장기적합비율", "pct", "cp_fixed"), _r("손실위험도가중자산비율", "pct", "cp_lossw"),
        ],
    },
    "유동성": {
        "title": "유동성 (단위: 억원, %)",
        "note": "유동성비율 = 잔존만기 3개월 이내 원화유동성자산 ÷ 잔존만기 3개월 이내 원화유동성부채(FISIS 유동성 통계)예요. 사채 비중 = 사채 ÷ 차입부채, 현금및예치금 비중 = 현금및예치금 ÷ 총자산이에요. "
                "차입금·사채 세부 항목은 2011.Q2부터 있어요.",
        "rows": [
            _r("잔존만기 3개월 이내 유동성자산", "eok", "lq_assets"), _r("잔존만기 3개월 이내 유동성부채", "eok", "lq_liab"), _r("유동성비율", "pct", "lq_ratio", 0, True),
            _r("현금및예치금", "eok", "bs_cashdep"), _r("현금및예치금/총자산", "pct", "bs_cashr"),
            _r("차입부채", "eok", "bs_borrow", 0, True), _r("차입금", "eok", "bs_b_loan", 1), _r("사채", "eok", "bs_bond", 1), _r("사채/차입부채", "pct", "bs_bondr"),
        ],
    },
    "수수료수익": {
        "title": "수수료수익 구성 (단위: 억원, %)",
        "note": "연도(12월) 열은 해당 연도 4개 분기 합계, 4분기 전·당분기 열은 해당 분기 금액이에요(FISIS 부문별 손익(수수료)). 신탁보수는 토지신탁·관리신탁·처분신탁·담보신탁·분양관리신탁·기타(금전신탁 포함)의 합이고, "
                "한기평의 비토지신탁수익 = 관리+처분+담보+분양관리+기타 신탁, 부수업무수익 = 집합투자기구운용보수+대리업무보수+기타 수수료예요. 점유율은 FISIS 14개사 합계 대비 비중(누계 기준)이에요.",
        "rows": [
            _r("수수료수익 합계", "eok", "is_f_total", 0, True, fy="is_f_total_ltm"), _r("신탁보수", "eok", "is_f_trust", 0, False, fy="is_f_trust_ltm"),
            _r("토지신탁", "eok", "is_f_land", 1, False, fy="is_f_land_ltm"), _r("담보신탁", "eok", "is_f_coll", 1, False, fy="is_f_coll_ltm"),
            _r("관리신탁", "eok", "is_f_mgmt", 1, False, fy="is_f_mgmt_ltm"), _r("처분신탁", "eok", "is_f_disp", 1, False, fy="is_f_disp_ltm"),
            _r("분양관리신탁", "eok", "is_f_pre", 1, False, fy="is_f_pre_ltm"), _r("기타(금전신탁 등)", "eok", "is_f_other_trust", 1, False, fy="is_f_other_trust_ltm"),
            _r("집합투자기구운용보수", "eok", "is_f_fund", 0, False, fy="is_f_fund_ltm"), _r("대리업무보수", "eok", "is_f_agent", 0, False, fy="is_f_agent_ltm"),
            _r("기타 수수료수익", "eok", "is_f_etc", 0, False, fy="is_f_etc_ltm"),
            _r("수수료수익 점유율", "pct", "ms_fee"), _r("토지신탁 수수료 점유율", "pct", "ms_land"),
        ],
    },
    "주요 지표": {
        "title": "주요 지표 (단위: 억원, %, 배)",
        "note": "연도(12월) 열은 해당 연도 값(손익은 4개 분기 합계), 4분기 전·당분기 열은 해당 분기 값이에요. 비율 정의는 각 하위탭 표 아래 설명을 참고하세요.",
        "rows": [
            _r("총자산", "eok", "bs_asset", 0, True), _r("자기자본", "eok", "bs_equity"),
            _r("영업수익", "eok", "is_rev", 0, False, fy="is_rev_ltm"), _r("충당금적립전영업이익(PPOP)", "eok", "is_ppop", 0, False, fy="is_ppop_ltm"),
            _r("당기순이익", "eok", "is_ni", 0, True, fy="is_ni_ltm"),
            _r("ROA", "pct", "pf_roa"), _r("ROE", "pct", "pf_roe"), _r("영업순이익률", "pct", "pf_nim"),
            _r("요주의이하자산비중", "pct", "aq_watchr"), _r("고정이하자산비중", "pct", "aq_subr"), _r("(충당금+자기자본)/요주의이하자산", "pct", "aq_cov"),
            _r("영업용순자본비율(NCR)", "pct", "cp_ncr"), _r("부채비율", "pct", "bs_dr"), _r("차입금의존도", "pct", "bs_borrowr"), _r("유동성비율", "pct", "lq_ratio"),
            _r("영업수익 점유율", "pct", "ms_rev"),
        ],
    },
}

EXTRA_TABLES = {
    "수익성": [{
        "title": "영업수익 구성 (단위: 억원, 누계)",
        "note": "한기평 방식 구성이에요. 토지신탁수익 = 토지신탁 수수료, 비토지신탁수익 = 관리·처분·담보·분양관리·기타 신탁 수수료, 부수업무수익 = 집합투자기구운용보수·대리업무보수·기타 수수료, "
                "기타 = 영업수익 - 위 항목(증권평가 및 처분이익 등)이에요. 증권평가 및 처분이익은 아래 '증권평가 및 처분이익' 행과 같아요.",
        "rows": [
            _r("영업수익", "eok", "is_rev_ytd", 0, True), _r("토지신탁수익", "eok", "is_m_land_ytd", 1), _r("비토지신탁수익", "eok", "is_m_nonland_ytd", 1),
            _r("부수업무수익", "eok", "is_m_aux_ytd", 1), _r("이자수익", "eok", "is_m_int_ytd", 1), _r("기타(증권평가 및 처분이익 등)", "eok", "is_m_oth_ytd", 1),
            _r("신탁계정대 이자수익(이자수익 중)", "eok", "is_r_tlint_ytd", 1),
        ],
    }],
    "유동성": [],
}

SECTION_TITLES = {
    "key": "주요 지표 추이 (비교선: 부동산신탁 전체)", "perf_trend": "회사별 추이", "pf": "수익성 추이 (비교선: 부동산신탁 전체)",
    "aq": "자산건전성 (회색 선: 부동산신탁 전체)", "cp": "자본적정성 (회색 선: 부동산신탁 전체)", "lq": "유동성·차입 (회색 선: 부동산신탁 전체)",
    "fee": "수수료수익", "bs": "재무상태표 (단위: 억원)", "is": "손익계산서 (단위: 억원, 당분기)",
}

BLUE, RED, GRAY, ORANGE, GREEN, NAVY, GOLD, PURPLE = "#2980B9", "#E8312F", "#A6A6A6", "#ED7D31", "#70AD47", "#1F3864", "#F5B301", "#8E44AD"


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
        ("key_nim", "영업순이익률", "%", "cmp3", {"k": "pf_nim"}),
        ("key_sub", "고정이하자산비중", "%", "cmp3", {"k": "aq_subr", "gray": True}),
        ("key_watch", "요주의이하자산비중", "%", "cmp3", {"k": "aq_watchr", "gray": True}),
        ("key_cov", "(충당금+자기자본)/요주의이하자산", "%", "cmp3", {"k": "aq_cov", "gray": True}),
        ("key_ncr", "영업용순자본비율(NCR)", "%", "cmp3", {"k": "cp_ncr", "gray": True}),
        ("key_dr", "부채비율", "%", "cmp3", {"k": "bs_dr", "gray": True}),
        ("key_lq", "유동성비율", "%", "cmp3", {"k": "lq_ratio", "gray": True}),
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
        ("pf_c_sga", "판관비/영업수익", "%", "cmp3", {"k": "pf_sga"}), ("pf_c_sgaa", "판관비용률 (판관비/총자산평잔)", "%", "cmp3", {"k": "pf_sgaa"}),
        ("pf_c_landsh", "토지신탁수익비중", "%", "cmp3", {"k": "pf_landsh"}),
        ("pf_c_mix", "영업수익 구성 (분기)", "억원", "stack",
         [("is_m_land", "토지신탁수익", BLUE), ("is_m_nonland", "비토지신탁수익", RED), ("is_m_aux", "부수업무수익", GOLD),
          ("is_m_int", "이자수익", GREEN), ("is_m_oth", "기타", GRAY)]),
        ("pf_c_ms", "영업수익 점유율 (누계 기준, 신탁사별)", "%", "allco", {"k": "ms_rev", "pair": 1}),
    ],
    "aq": [
        ("aq_c_sub", "고정이하자산비중", "%", "cmp3", {"k": "aq_subr", "gray": True}),
        ("aq_c_watch", "요주의이하자산비중", "%", "cmp3", {"k": "aq_watchr", "gray": True}),
        ("aq_c_cov", "(충당금+자기자본)/요주의이하자산", "%", "cmp3", {"k": "aq_cov", "gray": True}),
        ("aq_c_netsub", "자기자본 대비 순고정이하자산비율", "%", "cmp3", {"k": "aq_netsub", "gray": True}),
        ("aq_c_tlar", "신탁계정대충당금/신탁계정대", "%", "cmp3", {"k": "aq_tl_ar", "gray": True}),
        ("aq_c_tleq", "신탁계정대(순)/자기자본", "%", "cmp3", {"k": "aq_tl_eq", "gray": True}),
    ],
    "cp": [
        ("cp_c_ncr", "영업용순자본비율(NCR)", "%", "cmp3", {"k": "cp_ncr", "gray": True}),
        ("cp_c_dr", "부채비율", "%", "cmp3", {"k": "bs_dr", "gray": True}),
        ("cp_c_borrow", "차입금의존도", "%", "cmp3", {"k": "bs_borrowr", "gray": True}),
        ("cp_c_netborrow", "순차입금의존도", "%", "cmp3", {"k": "bs_netborrowr", "gray": True}),
        ("cp_c_lev", "총자산/자기자본 (레버리지)", "배", "cmp3", {"k": "bs_lev", "gray": True}),
    ],
    "lq": [
        ("lq_c_ratio", "유동성비율", "%", "cmp3", {"k": "lq_ratio", "gray": True}),
        ("lq_c_cash", "현금및예치금/총자산", "%", "cmp3", {"k": "bs_cashr", "gray": True}),
        ("lq_c_bondr", "사채/차입부채", "%", "cmp3", {"k": "bs_bondr", "gray": True}),
        ("lq_c_mix", "차입부채 구성", "억원", "stack", [("bs_b_loan", "차입금", BLUE), ("bs_bond", "사채", RED)]),
        ("lq_c_borrowr", "차입금의존도", "%", "cmp3", {"k": "bs_borrowr", "gray": True}),
    ],
    "fee": [
        ("fee_c_mix", "수수료수익 구성 (분기)", "억원", "stack",
         [("is_f_land", "토지신탁", BLUE), ("is_f_coll", "담보신탁", RED), ("is_f_mgmt", "관리신탁", GOLD), ("is_f_disp", "처분신탁", GREEN),
          ("is_f_pre", "분양관리신탁", NAVY), ("is_f_other_trust", "기타신탁", PURPLE), ("is_f_fund", "집합투자기구운용보수", ORANGE),
          ("is_f_agent", "대리업무보수", "#17A2B8"), ("is_f_etc", "기타 수수료", GRAY)]),
        ("fee_c_total", "수수료수익 합계 (분기)", "억원", "bar", None),
        ("fee_c_land", "토지신탁 수수료 (분기)", "억원", "bar", None),
        ("fee_c_coll", "담보신탁 수수료 (분기)", "억원", "bar", None),
        ("fee_c_mgmt", "관리신탁 수수료 (분기)", "억원", "bar", None),
        ("fee_c_ms", "수수료수익 점유율 (누계 기준, 신탁사별)", "%", "allco", {"k": "ms_fee", "pair": 1}),
        ("fee_c_msland", "토지신탁 수수료 점유율 (누계 기준, 신탁사별)", "%", "allco", {"k": "ms_land", "pair": 1}),
    ],
    "bs_top": [
        ("bt_asset", "부동산신탁사 총자산 구성 추이", "조원", "stackj", {"bars": [
            {"k": "bs_cashdep", "n": "현금및예치금", "c": "#2B2D6E"}, {"k": "bs_sec", "n": "유가증권", "c": "#92C1D6"},
            {"k": "bs_loan", "n": "대출채권(신탁계정대 포함)", "c": "#FFE699"}, {"k": "bs_tang", "n": "유형자산", "c": "#6B6EAF"},
            {"k": "bs_oth_a", "n": "기타자산", "c": "#BFBFBF"}]}),
        ("bt_liab", "부동산신탁사 부채·자본 구성 추이", "조원", "stackj", {"bars": [
            {"k": "bs_borrow", "n": "차입부채", "c": "#2B2D6E"}, {"k": "bs_oth_l", "n": "기타부채", "c": "#FFE699"},
            {"k": "bs_equity", "n": "자기자본", "c": "#6B6EAF"}]}),
        ("bt_tl", "신탁계정대 (장부가액 + 대손충당금)", "조원", "stackj", {"bars": [
            {"k": "bs_tl_net", "n": "신탁계정대(장부가액)", "c": "#2B2D6E"}, {"k": "bs_tl_allow", "n": "대손충당금", "c": "#E8B4B0"}]}),
    ],
    "bs": _row_charts(BS_ROWS),
    "is": _row_charts([(n, "eok", k, "is_" + k, i, b) for n, k, i, b in IS_ROWS]),
}
SERIES_KEY = {"pf_c_rev": "is_rev", "pf_c_cost": "is_cost", "pf_c_ppop": "is_ppop", "pf_c_dae": "is_dae", "pf_c_op": "is_op", "pf_c_ni": "is_ni",
              "pr_ni": "is_ni", "pr_rev": "is_rev", "pr_ppop": "is_ppop", "pf_c_ms": "ms_rev", "fee_c_total": "is_f_total", "fee_c_land": "is_f_land",
              "fee_c_coll": "is_f_coll", "fee_c_mgmt": "is_f_mgmt", "fee_c_ms": "ms_fee", "fee_c_msland": "ms_land"}
PAIRED = {"aq", "cp"}   # 차트마다 부동산신탁사별 비교 차트를 같은 순서로 아래에 붙이는 탭

CHART_NOTES = {
    "bt_asset": "선택 대상의 자산 구성이에요. 기타자산 = 총자산 - 나머지 항목이에요.",
    "bt_liab": "차입부채(차입금+사채)와 기타부채, 자기자본의 합이 총자산이에요.",
    "bt_tl": "신탁계정대(총액) = 장부가액 + 대손충당금이에요. 2011.Q2부터 FISIS에 있어요.",
    "pr_dual": "막대: 당기순이익(당분기, 좌축), 선: ROA(우축, 당분기 순이익 ×4 ÷ 총자산 분기 평잔).",
    "pf_c_rev": "차트는 모두 분기 개별 금액이에요(표는 연초부터의 누계). 회사를 고르면 부동산신탁 전체(FISIS 14개사 합산)와 비교하는 비율 차트가 함께 나와요. 2019.Q3~2019.Q4에 대신·한국투자·신영이 들어와 합산 규모가 늘어요.",
    "pf_c_ppopr": "PPOP/총자산평잔 = 당분기 PPOP ×4 ÷ 총자산 분기 평잔. 4분기 누적은 최근 4개 분기 PPOP ÷ 5개 분기말 평균 총자산이에요.",
    "pf_c_daer": "대손비용/총자산평잔(대손율) = 당분기 대손비용 ×4 ÷ 총자산 분기 평잔.",
    "pf_c_roa": "ROA = 당분기 당기순이익 ×4 ÷ 총자산 분기 평잔. 표의 ROA(누계 연환산)와 값이 달라요.",
    "pf_c_landsh": "토지신탁수익비중 = (토지신탁 수수료수익 + 신탁계정대 이자수익) ÷ 영업수익이에요.",
    "pf_c_mix": "한기평 방식 구성이에요(토지신탁수익·비토지신탁수익·부수업무수익·이자수익). 기타는 증권평가 및 처분이익 등이에요.",
    "pf_c_ms": "점유율 = 회사 영업수익(누계) ÷ FISIS 14개사 합계예요.",
    "aq_c_sub": "고정이하자산비중 = 고정이하(고정+회수의문+추정손실) ÷ 분류대상 자산. 분류대상 자산에는 신탁계정대가 가장 커서 이 비율은 사실상 신탁계정대 부실 정도를 보여줘요.",
    "aq_c_cov": "(충당금+자기자본)/요주의이하자산 = (대출채권 대손충당금+기타자산 대손충당금+자기자본) ÷ 요주의이하자산.",
    "aq_c_netsub": "자기자본 대비 순고정이하자산비율 = (고정이하자산 - 대손충당금) ÷ 자기자본.",
    "cp_c_ncr": "영업용순자본비율 = 영업용순자본 ÷ 총위험액 (FISIS 자본적정성 통계).",
    "cp_c_netborrow": "순차입금의존도 = (차입부채 - 현금및예치금) ÷ 총자산.",
    "fee_c_mix": "FISIS 부문별 손익(수수료) 기준이에요. 신탁보수 구성(토지·담보·관리·처분·분양관리·기타 신탁)과 집합투자기구운용보수·대리업무보수·기타 수수료예요.",
    "fee_c_ms": "점유율 = 회사 수수료수익(누계) ÷ FISIS 14개사 합계예요.",
}

# 회사별 비교 막대에서 고를 수 있는 지표
CBAR_KEY = [
    ("pf_roa", "ROA", "%"), ("pf_roe", "ROE", "%"), ("pf_nim", "영업순이익률", "%"), ("aq_subr", "고정이하자산비중", "%"),
    ("aq_watchr", "요주의이하자산비중", "%"), ("aq_cov", "(충당금+자기자본)/요주의이하자산", "%"), ("cp_ncr", "영업용순자본비율(NCR)", "%"),
    ("bs_dr", "부채비율", "%"), ("bs_borrowr", "차입금의존도", "%"), ("lq_ratio", "유동성비율", "%"),
    ("bs_asset", "총자산", "억원"), ("bs_equity", "자기자본", "억원"), ("bs_tl", "신탁계정대(총액)", "억원"), ("ms_rev", "영업수익 점유율", "%"),
]
CBAR_PERF = [
    ("is_ni", "당기순이익", "억원"), ("is_rev", "영업수익", "억원"), ("is_ppop", "충당금적립전영업이익(PPOP)", "억원"), ("is_op", "영업이익", "억원"),
    ("is_dae", "대손비용", "억원"), ("pf_roa", "ROA", "%"), ("pf_roe", "ROE", "%"),
]
CTABLE_COLS = [
    {"n": "영업수익", "k": "is_rev", "u": "eok"}, {"n": "PPOP", "k": "is_ppop", "u": "eok"}, {"n": "영업이익", "k": "is_op", "u": "eok"},
    {"n": "당기순이익", "k": "is_ni", "u": "eok"}, {"n": "당기순이익 전년동기대비", "k": "is_ni", "u": "pct", "yoy": True},
    {"n": "ROA", "k": "pf_roa", "u": "pct"}, {"n": "ROE", "k": "pf_roe", "u": "pct"}, {"n": "총자산", "k": "bs_asset", "u": "eok"},
]

# 한기평 Data Sheet 표지(2026.06): 한국토지신탁·한국자산신탁·하나자산신탁·신한자산신탁. 한신평 자료는 받지 못했고 NICE NDB에는 신용등급이 없어 비워둠.
RATINGS = {
    "한국토지신탁": ("A-(S)", None, None), "한국자산신탁": ("A-(S)", None, None), "하나자산신탁": ("A(S)", None, None), "신한자산신탁": ("A-(N)", None, None),
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
    if kind in ("dual", "cmp3", "cmp3m", "stackj", "scatter", "allco"):
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


def _grid(prefix, items, cols=COLUMNS):
    return f'<div class="grid" style="grid-template-columns:repeat({cols},1fr);">' + "".join(_cell(prefix, *it) for it in items) + "</div>"


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
        '<p class="caption">영업수익·PPOP·영업이익·당기순이익은 해당 분기(당분기) 금액, ROA·ROE는 누계 연환산 기준이에요.</p>'
    )


def _tables(tab):
    out = []
    if tab in TAB_TABLES:
        out.append(_table_html(TAB_TABLES[tab]))
    for et in EXTRA_TABLES.get(tab, []):
        out.append(_table_html(et))
    return "".join(out)


def render_list_tab(rows: list[dict], qlabel: str) -> str:
    """전체 리스트: FISIS 부동산신탁사별 총자산·자기자본·ROA·NCR·고정이하자산비중과 한기평 신용등급."""
    rows = sorted(rows, key=lambda r: -(r["asset"] or 0))
    body = []
    fmt_pct = lambda v: "" if v is None else f"{v:.2f}%"
    for i, r in enumerate(rows, 1):
        kr, kis, nice = RATINGS.get(r["name"], (None, None, None))
        cell = lambda v, d: f'<td data-v="{"" if v is None else v}">{d}</td>'
        body.append(
            "<tr>" + cell(i, i) + f'<td data-v="{r["name"]}">{r["name"]}</td>'
            + cell(r["asset"], "" if r["asset"] is None else f'{r["asset"]:,.0f}')
            + cell(r["equity"], "" if r["equity"] is None else f'{r["equity"]:,.0f}')
            + cell(r["roa"], fmt_pct(r["roa"])) + cell(r["ncr"], "" if r["ncr"] is None else f'{r["ncr"]:,.1f}%')
            + cell(r["sub"], fmt_pct(r["sub"]))
            + "".join(f'<td data-v="{_grade_rank(x)}" style="text-align:center;">{x or ""}</td>' for x in (kr, kis, nice))
            + "</tr>"
        )
    heads = ["No", "금융회사명", "총자산(억원)", "자기자본(억원)", "ROA", "영업용순자본비율", "고정이하자산비중", "한기평(KR)", "한신평", "NICE"]
    th = "".join(
        f'<th class="sortable" data-text="{1 if i == 1 else 0}"{" data-dir=" + chr(34) + "-1" + chr(34) if i == 2 else ""} '
        f'onclick="tblSort(this)">{h}<span class="sort-arrow">{" ▼" if i == 2 else ""}</span></th>'
        for i, h in enumerate(heads))
    return (
        f'<h4>부동산신탁사 전체 리스트 <span class="caption" style="font-weight:normal;">(재무는 {qlabel} 기준, 열 제목을 누르면 정렬)</span></h4>'
        f'<div style="overflow-x:auto;"><table class="data-table kis-ltable" id="trustListTable"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
        '<p class="caption">FISIS 부동산신탁사 14개예요. 총자산·자기자본·ROA·영업용순자본비율·고정이하자산비중은 FISIS 기준이고 ROA는 당기순이익(누계, 연환산) ÷ ((직전 결산말+해당 시점) 총자산 평균)이에요. '
        '신용등급은 한기평 Data Sheet 2026.06 기준 장기등급/전망(S=안정적, N=부정적)이고 한기평 자료에 있는 4개사만 채웠어요. 한신평 자료는 아직 없고 NICE 자료(NDB)에는 신용등급이 없어서 해당 열은 비어 있어요.</p>'
    )


def render_bodies(prefix: str, quarters: list[str], list_html: str = "") -> list[str]:
    ctl = render_controls()

    def sec(name):
        if name in PAIRED:   # 3열: 위는 선택 회사 비교 차트, 아래는 같은 지표 순서의 부동산신탁사별 비교 차트
            left = [(key, title, unit, kind, {**extra, "pair": 1}) for key, title, unit, kind, extra in SECTIONS[name]]
            right = [(key + "_all", title + " - 신탁사별", unit, "allco", {"k": extra["k"], "pair": 1}) for key, title, unit, kind, extra in SECTIONS[name]]
            return (f'<h4>{SECTION_TITLES[name]}</h4>' + _grid(prefix, left)
                    + '<h4>신탁사별 비교 (부동산신탁 전체 + 개별 신탁사)</h4>' + _grid(prefix, right))
        return f'<h4>{SECTION_TITLES[name]}</h4>' + _grid(prefix, SECTIONS[name])

    bodies = {
        "주요 지표": ctl + _tables("주요 지표") + _cbar(prefix, "cb_key", "회사별 지표 비교", CBAR_KEY, quarters) + sec("key"),
        "최근 실적": ctl + _cbar(prefix, "cb_perf", "회사별 실적 비교", CBAR_PERF, quarters) + sec("perf_trend") + _ctable("회사별 최신 실적"),
        "수익성": ctl + _tables("수익성") + sec("pf"),
        "자산건전성": ctl + _tables("자산건전성") + sec("aq"),
        "자본적정성": ctl + _tables("자본적정성") + sec("cp"),
        "유동성": ctl + _tables("유동성") + sec("lq"),
        "수수료수익": ctl + _tables("수수료수익") + sec("fee"),
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
