"""증권사 페이지 HTML(탭별 표/차트 자리) 생성. 데이터는 sec_data.py, 그리는 건 kis_charts.js(저축은행과 공용).

하위탭 순서: 주요 지표, 최근 실적, 수익성, 자산건전성, 자본적정성, 유동성, 파생결합증권, 재무상태표, 손익계산서.
표 양식(행 구성)은 엑셀 '증권사비교' 시트를 따르고, 회사 선택/기간 선택/표 열(연도 12월 5개 + 4분기 전 + 당분기)/
차트 3열·비교선은 상호저축은행과 같다. 비교선: 업권 전체(점선), 종합IB(파선), 일반증권사(쇄선).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kis_charts import PERIOD_PRESETS, _table_html  # noqa: E402
from sec_data import ALL_LABEL  # noqa: E402

TAB_LABELS = ["주요 지표", "최근 실적", "수익성", "자산건전성", "자본적정성", "유동성", "파생결합증권", "재무상태표", "손익계산서", "전체 리스트"]
COLUMNS = 3
DATA_ID = "kis-data-sec"
LIST_ID = "kisCompanyList-sec"

EXCEL_NOTE = ("(엑셀) 표시 항목은 FISIS에 없어 한국기업평가 증권업 재무자료(엑셀) 값을 썼어요. 엑셀에 있는 결산/분기 시점(2019.12~, 2024년부터 분기)만 값이 있어요.")


# ---------------------------------------------------------------- 표 정의
# (이름, 단위, 연도(12월) 열 키, 분기 열 키, 들여쓰기, 굵게)
def _r(name, unit, key, indent=0, bold=False, fy=None):
    return (name, unit, fy or key, key, indent, bold)


BS_ROWS = [
    _r("현금및현금성자산", "eok", "bs_cash"), _r("예치금", "eok", "bs_dep"), _r("증권", "eok", "bs_sec"),
    _r("(주식)", "eok", "bs_sec_stock", 1), _r("(국공채 및 특수채)", "eok", "bs_sec_gov", 1), _r("(회사채)", "eok", "bs_sec_corp", 1),
    _r("(기업어음)", "eok", "bs_sec_cp", 1), _r("(집합투자증권)", "eok", "bs_sec_fund", 1), _r("(외화증권)", "eok", "bs_sec_fx", 1),
    _r("(종속관계기업지분)", "eok", "bs_sec_assoc", 1), _r("(파생결합증권)", "eok", "bs_sec_dlsec", 1), _r("(기타)", "eok", "bs_sec_etc", 1),
    _r("(대손충당금 등)", "eok", "bs_sec_allow", 1),
    _r("파생상품자산", "eok", "bs_deriv_a"), _r("대출채권", "eok", "bs_loan"),
    _r("(콜론및RP매수)", "eok", "bs_ln_call", 1), _r("(신용공여금)", "eok", "bs_ln_margin", 1), _r("(기업여신)", "eok", "bs_ln_corp", 1),
    _r("(종금계정-대출금,할인어음)", "eok", "bs_ln_jg", 1), _r("(기타)", "eok", "bs_ln_etc", 1), _r("(대손충당금 등)", "eok", "bs_ln_allow", 1),
    _r("기타자산", "eok", "bs_oth_a"), _r("(미수금)", "eok", "bs_oth_recv", 1), _r("(기타)", "eok", "bs_oth_etc", 1),
    _r("(대손충당금 등)", "eok", "bs_oth_allow", 1),
    _r("자산 합계", "eok", "bs_asset", 0, True),
    _r("예수부채", "eok", "bs_dep_l"), _r("(투자자예수금)", "eok", "bs_dep_inv", 1),
    _r("실질차입부채", "eok", "bs_borrow_real"), _r("(콜머니)", "eok", "bs_b_call", 1), _r("(차입금)", "eok", "bs_b_loan", 1),
    _r("(사채)", "eok", "bs_b_bond", 1), _r("(후순위사채)", "eok", "bs_b_sub", 1),
    _r("대고객차입부채", "eok", "bs_client"), _r("(RP매도)", "eok", "bs_cb_rp", 1), _r("(매도증권)", "eok", "bs_cb_sec", 1),
    _r("(매도파생결합증권)", "eok", "bs_cb_dls", 1), _r("(종금계정, 종합금융투자사업자-발행어음)", "eok", "bs_cb_note", 1),
    _r("(IMA)", "eok", "bs_cb_ima", 1),
    _r("파생상품부채", "eok", "bs_deriv_l"), _r("기타부채", "eok", "bs_oth_l"), _r("(미지급금)", "eok", "bs_oth_l_pay", 1),
    _r("(기타)", "eok", "bs_oth_l_etc", 1),
    _r("부채총계", "eok", "bs_liab", 0, True), _r("자기자본", "eok", "bs_equity", 0, True), _r("(자본금)", "eok", "bs_capital", 1),
    _r("부채 및 자본총계", "eok", "bs_total", 0, True),
]

IS_ROWS = [
    ("영업수익", "is_rev", 0, True), ("(수수료수익)", "is_r_fee", 1, False), ("(증권평가및처분이익)", "is_r_sec", 1, False),
    ("(파생상품거래이익)", "is_r_der", 1, False), ("(이자수익 및 기타)", "is_r_int", 1, False),
    ("영업비용", "is_cost", 0, True), ("(수수료비용)", "is_c_fee", 1, False), ("(증권평가및처분손실)", "is_c_sec", 1, False),
    ("(파생상품거래손실)", "is_c_der", 1, False), ("(이자비용 및 기타)", "is_c_int", 1, False),
    ("영업순수익", "is_net", 0, True), ("(충당금적립액)", "is_prov", 1, False), ("(판매비와 관리비)", "is_sga", 1, False),
    ("영업이익", "is_op", 0, True), ("영업외수익", "is_nonop_r", 0, False), ("영업외비용", "is_nonop_c", 0, False),
    ("법인세비용차감전순이익", "is_pretax", 0, False), ("당기순이익", "is_ni", 0, True),
]

TAB_TABLES = {
    "재무상태표": {
        "title": "요약 재무상태표 (단위: 억원)",
        "note": "연도(12월) 열은 해당 연도 12월 말, 4분기 전·당분기 열은 해당 분기 말 값이에요. 2011.Q2부터 있어요. "
                "회사 재분류(증권 유형별 구분, 대출채권 중 기업여신 등)는 엑셀 양식을 따랐고 일부 회사는 엑셀과 몇 억원 차이가 날 수 있어요. "
                "기타자산 = 자산총계 - 위 항목들, IMA = 부채총계 - 예수부채·차입부채·파생상품부채·기타부채 잔여분이에요. "
                "자료: FISIS(업무보고서). 신영증권은 3월 결산법인이에요.",
        "rows": BS_ROWS,
    },
    "손익계산서": {
        "title": "요약 손익계산서 (단위: 억원)",
        "note": "연도(12월) 열은 해당 연도 4개 분기 합계, 4분기 전·당분기 열은 해당 분기 금액(당분기)이에요. 적용 재무제표는 별도, 회계기준은 IFRS예요. "
                "영업수익/영업비용은 대출채권 관련 손익·기타대손충당금·충당부채 전입(환입)액을 제외한 금액이고, "
                "영업순수익 = 영업수익 - 영업비용, 영업이익 = 영업순수익 - 충당금적립액 - 판매비와 관리비예요. "
                "자료: FISIS(업무보고서). 신영증권은 3월 결산법인(회계연도 4월~)이에요.",
        "rows": [(n, "eok", k + "_ltm", k, i, b) for n, k, i, b in IS_ROWS],
    },
    "수익성": {
        "title": "수익성 (단위: 억원, %)",
        "note": "영업순수익 구성(위탁매매·상품운용·투자은행·자산관리·기타)은 FISIS에 없어 엑셀 값이고, 연초부터의 누계 기준이에요. " + EXCEL_NOTE + " "
                "영업순수익 점유율 = 영업순수익(누계) ÷ FISIS 증권사 전체(외국계 지점 포함) 영업순수익 합계. ROA = 당기순이익(누계, 연환산) ÷ ((직전 결산말+해당 시점) 총자산 평균), "
                "ROE는 자기자본 기준(분·반기는 연환산)이고, 판관비/영업순수익 = 판매관리비 ÷ 영업순수익(누계)이에요.",
        "rows": [
            _r("위탁매매", "eok", "ex_brokerage", 1), _r("상품운용", "eok", "ex_trading", 1), _r("투자은행", "eok", "ex_ib", 1),
            _r("자산관리", "eok", "ex_wm", 1), _r("기타", "eok", "ex_otherrev", 1),
            _r("영업순수익 (누계)", "eok", "is_net_ytd", 0, True), _r("영업순수익 점유율", "pct", "pf_share"),
            _r("총자산이익률(ROA)", "pct", "pf_roa"), _r("자기자본이익률(ROE)", "pct", "pf_roe"), _r("판관비/영업순수익", "pct", "pf_sga"),
        ],
    },
    "자산건전성": {
        "title": "자산건전성 (단위: 억원, %)",
        "note": "건전성분류대상자산 = 자산건전성 분류 합계, 요주의이하 = 요주의+고정+회수의문+추정손실, 고정이하 = 고정+회수의문+추정손실이에요. "
                "대손충당금은 FISIS 재무상태표의 대출채권·기타자산(·증권) 대손충당금 합계라서, 기타포괄손익-공정가치측정증권 손실충당금 등이 들어간 엑셀보다 작을 수 있어요. "
                "순요주의이하여신/자기자본 = (요주의이하-대손충당금) ÷ 자기자본, 순고정이하여신/자기자본 = (고정이하-대손충당금) ÷ 자기자본이에요.",
        "rows": [
            _r("건전성분류대상자산", "eok", "aq_total"), _r("요주의이하", "eok", "aq_watch"), _r("고정이하", "eok", "aq_sub"),
            _r("대손충당금", "eok", "aq_allow"), _r("순요주의이하여신/자기자본", "pct", "aq_nwatch"), _r("순고정이하여신/자기자본", "pct", "aq_nsub"),
        ],
    },
    "자본적정성": {
        "title": "자본적정성 (단위: 억원, %, 배)",
        "note": "연도(12월) 열은 해당 연도 12월 말, 4분기 전·당분기 열은 해당 분기 말 값이에요. 순자본비율 = (영업용순자본-총위험액) ÷ 필요유지자기자본, "
                "규제레버리지배율 = 총자산 ÷ 자기자본(금융투자업규정시행세칙 기준)이에요. 영업용순자본·총위험액·필요유지자기자본은 연결기준(2016.Q1~)이고 "
                "그 전(2015.Q1~)은 개별기준이에요. " + EXCEL_NOTE + " 수정NCR = 수정영업용순자본 ÷ 수정총위험액이에요.",
        "rows": [
            _r("영업용순자본(연결)", "eok", "cp_ncap"), _r("수정영업용순자본(연결) (엑셀)", "eok", "ex_adj_ncap"),
            _r("총위험액(연결)", "eok", "cp_risk"), _r("수정총위험액(연결) (엑셀)", "eok", "ex_adj_risk"),
            _r("필요유지자기자본(연결)", "eok", "cp_req"), _r("수정NCR (엑셀)", "pct", "ex_adj_ncr"), _r("순자본비율", "pct", "cp_ncr"),
            _r("조정레버리지배율 (엑셀)", "x", "ex_adj_lev"), _r("규제레버리지배율", "x", "cp_lev"),
        ],
    },
    "유동성": {
        "title": "유동성 (단위: 억원, %)",
        "note": "유동성자산·유동성부채는 잔존만기 3개월 이내 기준이고(FISIS 유동성 통계), 유동성비율 = 유동성자산 ÷ 유동성부채예요. " + EXCEL_NOTE + " "
                "조정유동성비율 = 유동성자산 ÷ (유동성부채+유동화 관련 우발채무 및 미사용한도대출약정)이에요.",
        "rows": [
            _r("유동성자산", "eok", "lq_assets"), _r("유동성부채", "eok", "lq_liab"), _r("유동성GAP(유동성자산-유동성부채)", "eok", "lq_gap"),
            _r("유동성비율", "pct", "lq_ratio"), _r("조정유동성비율 (엑셀)", "pct", "ex_adj_liq"), _r("우발채무/유동성GAP (엑셀)", "pct", "ex_cont_gap"),
        ],
    },
    "주요 지표": {
        "title": "주요 지표 (단위: 억원, %, 배)",
        "note": "연도(12월) 열은 해당 연도 값(손익은 4개 분기 합계), 4분기 전·당분기 열은 해당 분기 값이에요. 비율 정의는 각 하위탭 표 아래 설명을 참고하세요.",
        "rows": [
            _r("자산 합계", "eok", "bs_asset", 0, True), _r("자기자본", "eok", "bs_equity"),
            _r("영업순수익", "eok", "is_net", 0, False, fy="is_net_ltm"), _r("당기순이익", "eok", "is_ni", 0, True, fy="is_ni_ltm"),
            _r("총자산이익률(ROA)", "pct", "pf_roa"), _r("자기자본이익률(ROE)", "pct", "pf_roe"), _r("판관비/영업순수익", "pct", "pf_sga"),
            _r("순요주의이하여신/자기자본", "pct", "aq_nwatch"), _r("순자본비율", "pct", "cp_ncr"), _r("규제레버리지배율", "x", "cp_lev"),
            _r("유동성비율", "pct", "lq_ratio"),
        ],
    },
}

EXTRA_TABLES = {
    "유동성": [{
        "title": "우발채무 (단위: 억원, %)",
        "note": EXCEL_NOTE + " 우발채무/자기자본 = 우발채무 ÷ 자기자본이에요.",
        "rows": [_r("우발채무 (엑셀)", "eok", "ex_cont"), _r("우발채무/자기자본 (엑셀)", "pct", "ex_cont_eq")],
    }],
    "파생결합증권": [{
        "title": "파생결합증권 (단위: 억원, %)",
        "note": EXCEL_NOTE + " 자체헤지 ELS·DLS/자기자본 = 자체헤지 ELS·DLS ÷ 자기자본, /유동성GAP = 자체헤지 ELS·DLS ÷ 유동성GAP(유동성자산-유동성부채)이에요. "
                "재무상태표상 파생결합증권(자산)·매도파생결합증권(부채)은 FISIS 값이에요.",
        "rows": [
            _r("ELS·ELB (엑셀)", "eok", "ex_els"), _r("DLS·DLB (엑셀)", "eok", "ex_dls"), _r("자체헤지 ELS·DLS (엑셀)", "eok", "ex_hedge"),
            _r("자체헤지 ELS·DLS/자기자본 (엑셀)", "pct", "ex_hedge_eq"), _r("자체헤지 ELS·DLS/유동성GAP (엑셀)", "pct", "ex_hedge_gap"),
            _r("(재무상태표) 파생결합증권", "eok", "dr_asset"), _r("(재무상태표) 매도파생결합증권", "eok", "dr_sold"),
        ],
    }],
}

SECTION_TITLES = {
    "perf_trend": "회사별 추이",
    "pf": "수익성 추이 (비교선: 업권 전체·종합IB·일반증권사)",
    "aq": "자산건전성 (회색 선: 업권 전체·종합IB·일반증권사)",
    "cp": "자본적정성 (비교선: 업권 전체·종합IB·일반증권사)",
    "lq": "유동성 (회색 선: 업권 전체·종합IB·일반증권사)",
    "dr": "파생결합증권",
    "bs": "재무상태표 (단위: 억원)",
    "is": "손익계산서 (단위: 억원, 당분기)",
    "key": "주요 지표 추이 (비교선: 업권 전체·종합IB·일반증권사)",
}

BLUE, RED, GRAY, ORANGE, GREEN, NAVY, GOLD = "#2980B9", "#E8312F", "#A6A6A6", "#ED7D31", "#70AD47", "#1F3864", "#F5B301"

# 섹션: [(키, 이름, 단위, 차트종류, 추가정보)]  (종류: bar/line/cmp3/cmp3m/dual/multi/stack/empty)
def _bs_charts():
    out, parent = [], ""
    for name, unit, fy, key, indent, bold in BS_ROWS:
        if indent == 0:
            parent = name
        if key == "bs_sec_allow":
            continue
        title = name if indent == 0 else f"{parent} - {name.strip('()')}"
        out.append((key, title, "억원", "bar", None))
    return out


_BS_CHARTS = _bs_charts()
SECTIONS = {
    "pf": [
        ("pf_c_comp", "영업순수익 구성 (누계)", "억원", "stack",
         [("ex_brokerage", "위탁매매", BLUE), ("ex_trading", "상품운용", RED), ("ex_ib", "투자은행", GOLD), ("ex_wm", "자산관리", GREEN),
          ("ex_otherrev", "기타", GRAY)]),
        ("pf_c_compsh", "영업순수익 구성 비중", "%", "stack",
         [("ex_brokerage_sh", "위탁매매", BLUE), ("ex_trading_sh", "상품운용", RED), ("ex_ib_sh", "투자은행", GOLD),
          ("ex_wm_sh", "자산관리", GREEN), ("ex_otherrev_sh", "기타", GRAY)]),
        ("pf_c_share", "영업순수익 점유율", "%", "line", None),
        ("pf_c_roa", "총자산이익률(ROA)", "%", "cmp3", {"k": "pf_roa"}),
        ("pf_c_roe", "자기자본이익률(ROE)", "%", "cmp3", {"k": "pf_roe"}),
        ("pf_c_sga", "판관비/영업순수익", "%", "cmp3", {"k": "pf_sga"}),
    ],
    "aq": [
        ("aq_c_nwatch", "순요주의이하여신/자기자본", "%", "cmp3", {"k": "aq_nwatch", "gray": True}),
        ("aq_c_nsub", "순고정이하여신/자기자본", "%", "cmp3", {"k": "aq_nsub", "gray": True}),
        ("aq_c_watchr", "요주의이하비율", "%", "cmp3", {"k": "aq_watch_r", "gray": True}),
        ("aq_c_subr", "고정이하비율", "%", "cmp3", {"k": "aq_sub_r", "gray": True}),
        ("aq_c_cov", "대손충당금/고정이하", "%", "cmp3", {"k": "aq_cov", "gray": True}),
        ("e_aq1", "", "", "empty", None),
        ("aq_total", "건전성분류대상자산", "억원", "bar", None),
        ("aq_watch", "요주의이하", "억원", "bar", None),
        ("aq_sub", "고정이하", "억원", "bar", None),
        ("aq_allow", "대손충당금", "억원", "bar", None),
    ],
    "cp": [
        ("cp_c_ncr", "순자본비율", "%", "cmp3", {"k": "cp_ncr", "gray": True}),
        ("cp_c_adjncr", "수정NCR (엑셀)", "%", "cmp3", {"k": "ex_adj_ncr", "gray": True}),
        ("cp_c_lev", "규제레버리지배율", "배", "cmp3", {"k": "cp_lev", "gray": True}),
        ("cp_c_adjlev", "조정레버리지배율 (엑셀)", "배", "cmp3", {"k": "ex_adj_lev", "gray": True}),
        ("mc_cp_amt", "영업용순자본·총위험액 추이", "억원", "multi",
         [("cp_ncap", "영업용순자본", BLUE), ("cp_risk", "총위험액", RED), ("cp_req", "필요유지자기자본", GRAY)]),
        ("mc_cpadj_amt", "수정영업용순자본·수정총위험액 (엑셀)", "억원", "multi",
         [("ex_adj_ncap", "수정영업용순자본", BLUE), ("ex_adj_risk", "수정총위험액", RED)]),
    ],
    "lq": [
        ("lq_c_ratio", "유동성비율", "%", "cmp3", {"k": "lq_ratio", "gray": True}),
        ("lq_c_adj", "조정유동성비율 (엑셀)", "%", "cmp3", {"k": "ex_adj_liq", "gray": True}),
        ("mc_lq_amt", "유동성자산·유동성부채 추이", "억원", "multi",
         [("lq_assets", "유동성자산", BLUE), ("lq_liab", "유동성부채", RED)]),
        ("lq_gap", "유동성GAP", "억원", "bar", None),
        ("lq_c_contgap", "우발채무/유동성GAP (엑셀)", "%", "cmp3", {"k": "ex_cont_gap", "gray": True}),
        ("ex_cont", "우발채무 (엑셀)", "억원", "bar", None),
        ("lq_c_conteq", "우발채무/자기자본 (엑셀)", "%", "cmp3", {"k": "ex_cont_eq", "gray": True}),
    ],
    "dr": [
        ("mc_dr_els", "ELS·ELB / DLS·DLB (엑셀)", "억원", "multi", [("ex_els", "ELS·ELB", BLUE), ("ex_dls", "DLS·DLB", RED)]),
        ("ex_hedge", "자체헤지 ELS·DLS (엑셀)", "억원", "bar", None),
        ("dr_c_hedgeeq", "자체헤지 ELS·DLS/자기자본 (엑셀)", "%", "cmp3", {"k": "ex_hedge_eq", "gray": True}),
        ("dr_c_hedgegap", "자체헤지 ELS·DLS/유동성GAP (엑셀)", "%", "cmp3", {"k": "ex_hedge_gap", "gray": True}),
        ("mc_dr_bs", "재무상태표상 파생결합증권 (FISIS)", "억원", "multi", [("dr_asset", "파생결합증권(자산)", BLUE), ("dr_sold", "매도파생결합증권(부채)", RED)]),
    ],
    "bs": [(k, n, u, kind, ex) for k, n, u, kind, ex in _BS_CHARTS],
    "is": [(k, n.strip("()"), "억원", "bar", None) for n, k, i, b in IS_ROWS],
    "key": [
        ("key_roa", "총자산이익률(ROA)", "%", "cmp3", {"k": "pf_roa"}),
        ("key_roe", "자기자본이익률(ROE)", "%", "cmp3", {"k": "pf_roe"}),
        ("key_sga", "판관비/영업순수익", "%", "cmp3", {"k": "pf_sga"}),
        ("key_nwatch", "순요주의이하여신/자기자본", "%", "cmp3", {"k": "aq_nwatch", "gray": True}),
        ("key_ncr", "순자본비율", "%", "cmp3", {"k": "cp_ncr", "gray": True}),
        ("key_lev", "규제레버리지배율", "배", "cmp3", {"k": "cp_lev", "gray": True}),
        ("key_lq", "유동성비율", "%", "cmp3", {"k": "lq_ratio", "gray": True}),
        ("key_share", "영업순수익 점유율", "%", "line", None),
    ],
    "perf_trend": [
        ("pr_ni", "당기순이익", "억원", "bar", None),
        ("pr_net", "영업순수익", "억원", "bar", None),
        ("pr_dual", "당기순이익 / ROA", "억원 / %", "dual", {"bar": "is_ni", "line": "pf_roa", "bn": "당기순이익", "ln": "ROA(우)"}),
        ("pr_dc", "주요 손익 구성 (총자산 대비 %, 분기 연율화)", "%", "stack",
         [("dc_fee", "수수료손익", BLUE), ("dc_sec", "증권평가·처분손익", "#9DC3E6"), ("dc_der", "파생상품손익", GOLD),
          ("dc_int", "이자손익 및 기타", GREEN), ("dc_sga", "판관비", "#111111"), ("dc_prov", "충당금", RED)]),
        ("pr_roe", "자기자본이익률(ROE)", "%", "cmp3", {"k": "pf_roe"}),
        ("pr_roa", "총자산이익률(ROA)", "%", "cmp3", {"k": "pf_roa"}),
    ],
}
# 차트 키와 시리즈 키가 다른 단순 차트(bar/line)의 실제 시리즈 키
SERIES_KEY = {"pf_c_share": "pf_share", "key_share": "pf_share", "pr_ni": "is_ni", "pr_net": "is_net", "lq_gap": "lq_gap"}

CHART_NOTES = {
    "pf_c_comp": "엑셀(한국기업평가 증권업 재무자료)의 영업순수익 구성이에요. 해당 시점만 있고 연초부터의 누계 기준이에요. FISIS에 없는 항목이에요.",
    "pf_c_share": "영업순수익 점유율 = 해당 회사 영업순수익(누계) ÷ FISIS 증권사 전체(외국계 지점 포함) 영업순수익 합계. 선택 회사 선만 그려요(업권 전체를 고르면 분석 대상 26개사의 합산 점유율).",
    "pf_c_roa": "ROA = 당기순이익(누계, 연환산) ÷ ((직전 결산말 총자산+해당 시점 총자산) ÷ 2). 분·반기 시점은 연환산이에요. 회사를 고르면 업권 전체·종합IB·일반증권사와 비교해요.",
    "pf_c_roe": "ROE = 당기순이익(누계, 연환산) ÷ ((직전 결산말 자기자본+해당 시점 자기자본) ÷ 2).",
    "pf_c_sga": "판관비/영업순수익 = 판매비와 관리비 ÷ 영업순수익(모두 누계).",
    "aq_c_nwatch": "순요주의이하여신/자기자본 = (요주의이하-대손충당금) ÷ 자기자본. 대손충당금은 재무상태표 기준이라 엑셀과 차이가 있어요.",
    "aq_c_nsub": "순고정이하여신/자기자본 = (고정이하-대손충당금) ÷ 자기자본. 음수면 충당금이 고정이하여신보다 많다는 뜻이에요.",
    "aq_c_watchr": "요주의이하비율 = 요주의이하 ÷ 건전성분류대상자산.",
    "aq_c_subr": "고정이하비율 = 고정이하 ÷ 건전성분류대상자산.",
    "aq_c_cov": "대손충당금/고정이하 = 대손충당금(재무상태표 기준) ÷ 고정이하.",
    "cp_c_ncr": "순자본비율 = (영업용순자본-총위험액) ÷ 필요유지자기자본 (연결기준, 2015.Q1~2015.Q4는 개별기준).",
    "cp_c_adjncr": "수정NCR = 수정영업용순자본 ÷ 수정총위험액. 엑셀 값이라 해당 시점만 있어요.",
    "cp_c_lev": "규제레버리지배율 = 총자산 ÷ 자기자본 (금융투자업규정시행세칙 기준 산정액).",
    "cp_c_adjlev": "조정레버리지배율은 (총자산-투자자예치금-종금계정자산-위탁매매 등 일시계상 미수금+신용공여형 우발채무) ÷ 자기자본이에요. 엑셀 값이라 해당 시점만 있어요. 업권 합산은 자기자본 가중평균이에요.",
    "lq_c_ratio": "유동성비율 = 잔존만기 3개월 이내 유동성자산 ÷ 유동성부채 (FISIS 유동성 통계).",
    "lq_c_adj": "조정유동성비율 = 유동성자산 ÷ (유동성부채+유동화 관련 우발채무 및 미사용한도대출약정). 엑셀 값이라 해당 시점만 있어요.",
    "lq_c_contgap": "우발채무/유동성GAP은 엑셀 값이라 업권 합산 비교선이 없어요.",
    "pr_dc": "이자손익 및 기타에는 외환손익·기타영업손익이 들어 있어요. 이익은 위로, 비용(판관비·충당금)은 아래로 쌓여요.",
    "pr_dual": "막대: 당기순이익(당분기, 좌축), 선: ROA(우축, 누계 연환산 기준).",
    "pr_ni": "당기순이익은 당분기 금액이에요.",
    "pr_net": "영업순수익 = 영업수익 - 영업비용 (대출채권 관련 손익·기타대손충당금·충당부채 전입액 제외).",
    "key_nwatch": "대손충당금은 재무상태표 기준이에요.",
}

# 회사별 비교 막대(주요 지표 / 최근 실적)에서 고를 수 있는 지표: (키, 이름, 단위)
CBAR_KEY = [
    ("pf_roa", "총자산이익률(ROA)", "%"), ("pf_roe", "자기자본이익률(ROE)", "%"), ("pf_sga", "판관비/영업순수익", "%"),
    ("aq_nwatch", "순요주의이하여신/자기자본", "%"), ("aq_nsub", "순고정이하여신/자기자본", "%"), ("aq_sub_r", "고정이하비율", "%"),
    ("cp_ncr", "순자본비율", "%"), ("cp_lev", "규제레버리지배율", "배"), ("lq_ratio", "유동성비율", "%"),
    ("pf_share", "영업순수익 점유율", "%"), ("bs_asset", "자산 합계", "억원"), ("bs_equity", "자기자본", "억원"),
]
CBAR_PERF = [
    ("is_ni", "당기순이익", "억원"), ("is_net", "영업순수익", "억원"), ("is_op", "영업이익", "억원"), ("is_rev", "영업수익", "억원"),
    ("pf_roa", "총자산이익률(ROA)", "%"), ("pf_roe", "자기자본이익률(ROE)", "%"), ("pf_share", "영업순수익 점유율", "%"),
]
CTABLE_COLS = [
    {"n": "영업수익", "k": "is_rev", "u": "eok"}, {"n": "영업순수익", "k": "is_net", "u": "eok"}, {"n": "영업이익", "k": "is_op", "u": "eok"},
    {"n": "당기순이익", "k": "is_ni", "u": "eok"}, {"n": "당기순이익 전년동기대비", "k": "is_ni", "u": "pct", "yoy": True},
    {"n": "ROA", "k": "pf_roa", "u": "pct"}, {"n": "ROE", "k": "pf_roe", "u": "pct"}, {"n": "영업순수익 점유율", "k": "pf_share", "u": "pct"},
    {"n": "자산 합계", "k": "bs_asset", "u": "eok"},
]


# ---------------------------------------------------------------- HTML
def render_controls(allow_target: bool = False) -> str:
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
    if kind in ("dual", "cmp3", "cmp3m"):
        attrs = f" data-{kind}='{json.dumps(extra, ensure_ascii=False)}'"
    elif kind in ("multi", "stack"):
        spec = [{"k": k, "n": n, "c": c} for k, n, c in extra]
        attrs = f" data-{kind}='{json.dumps(spec, ensure_ascii=False)}'"
    series_key = SERIES_KEY.get(key, key)
    note = CHART_NOTES.get(key) or ""
    note_html = f'<p class="caption kis-note">{note}</p>' if note else ""
    ctype = "line" if kind == "line" else kind
    return (
        f'<div class="cell"><div class="kis-title">{name} <span>({unit})</span></div>'
        f'<div id="kis-{prefix}-{key}" class="plotly-chart kis-chart" data-key="{series_key}" data-type="{ctype}" '
        f'data-name="{name}" data-unit="{unit}" data-share=""{attrs}></div>{note_html}</div>'
    )


def _grid(prefix, items):
    cells = "".join(_cell(prefix, *it) for it in items)
    return f'<div class="grid" style="grid-template-columns:repeat({COLUMNS},1fr);">{cells}</div>'


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
        '<p class="caption">영업수익·영업순수익·영업이익·당기순이익은 해당 분기(당분기) 금액, ROA·ROE는 누계 연환산 기준이에요. 신영증권은 3월 결산법인이에요.</p>'
    )


def _tables(tab):
    out = []
    t = TAB_TABLES.get(tab)
    if t:
        out.append(_table_html(t))
    for et in EXTRA_TABLES.get(tab, []):
        out.append(_table_html(et))
    return "".join(out)


GRADE_ORDER = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B", "B-"]


def _grade_rank(rating: str | None) -> str:
    """등급 문자열의 장기등급 순위(높을수록 좋음). 장기등급이 없으면(단기등급만) 빈 값."""
    if not rating:
        return ""
    head = rating.replace("(단기)", "").split("/")[0]
    head = head.split("(")[0].strip()
    return str(len(GRADE_ORDER) - GRADE_ORDER.index(head)) if head in GRADE_ORDER else ""


def render_list_tab(rows: list[dict], qlabel: str) -> str:
    """전체 리스트: 현존 증권사별 대형/중소형 분류(3사 기준 통합), 총자산·자기자본·ROA, 3사 신용등급."""
    peers_path = Path(__file__).resolve().parent.parent / "data" / "securities_peers.json"
    if not peers_path.exists():
        return '<p class="caption">대형/중소형 분류 자료(data/securities_peers.json)가 없어요.</p>'
    peers = json.loads(peers_path.read_text(encoding="utf-8"))
    src_names = {"KR": "한기평", "KIS": "한신평", "NICE": "NICE"}
    out = []
    for r in rows:
        c = str(r["code"])
        tags, sizes = [], []
        for k in ("KR", "KIS", "NICE"):
            g = peers[k]["groups"].get(c)
            if g:
                label = peers[k].get("detail", {}).get(c) or ("종합IB" if k == "KR" and g == "대형" else "일반증권사" if k == "KR" else g)
                tags.append(f"{src_names[k]}: {label}")
                sizes.append(g)
        big = "대형" in sizes
        small = (not big) and "중소형" in sizes
        out.append({**r, "big": big, "small": small, "tip": " / ".join(tags),
                    "KR": peers["KR"]["ratings"].get(c), "KIS": peers["KIS"]["ratings"].get(c), "NICE": peers["NICE"]["ratings"].get(c)})
    out.sort(key=lambda x: -(x["asset"] or 0))
    n_big, n_small = sum(1 for x in out if x["big"]), sum(1 for x in out if x["small"])
    n_none = len(out) - n_big - n_small

    def td(text, v="", cls=""):
        return f'<td data-v="{v}"{f" class={chr(34)}{cls}{chr(34)}" if cls else ""}>{text}</td>'

    def num(x, d=0):
        return "" if x is None else f"{x:,.{d}f}"

    body = []
    for i, x in enumerate(out, 1):
        mark = lambda on: "○" if on else ""
        body.append(
            "<tr>" + td(i, i)
            + f'<td data-v="{x["name"]}" title="{x["tip"]}">{x["name"]}</td>'
            + f'<td data-v="{1 if x["big"] else 0}" style="text-align:center;" title="{x["tip"]}">{mark(x["big"])}</td>'
            + f'<td data-v="{1 if x["small"] else 0}" style="text-align:center;" title="{x["tip"]}">{mark(x["small"])}</td>'
            + td(num(x["asset"]), "" if x["asset"] is None else x["asset"])
            + td(num(x["equity"]), "" if x["equity"] is None else x["equity"])
            + td("" if x["roa"] is None else f'{x["roa"]:.2f}%', "" if x["roa"] is None else x["roa"])
            + "".join(f'<td data-v="{_grade_rank(x[k])}" style="text-align:center;">{x[k] or ""}</td>' for k in ("KR", "KIS", "NICE"))
            + "</tr>"
        )
    heads = ["No", "금융회사명", "대형", "중소형", "총자산(억원)", "자기자본(억원)", "ROA", "한기평(KR)", "한신평", "NICE"]
    text_cols = {1}
    th = "".join(
        f'<th class="sortable" data-text="{1 if i in text_cols else 0}"{" data-dir=" + chr(34) + "-1" + chr(34) if i == 4 else ""} '
        f'onclick="tblSort(this)">{h}<span class="sort-arrow">{" ▼" if i == 4 else ""}</span></th>'
        for i, h in enumerate(heads))
    return (
        f'<h4>증권사 전체 리스트 <span class="caption" style="font-weight:normal;">(재무는 {qlabel} 기준, 열 제목을 누르면 정렬)</span></h4>'
        f'<p class="caption">현존 증권사 {len(out)}개사 중 대형 {n_big}개, 중소형 {n_small}개, 3사 모두 분류하지 않은 회사 {n_none}개(외국계 지점 등)예요. '
        '회사명/○에 마우스를 올리면 3사가 각각 어떻게 분류했는지 보여요.</p>'
        f'<div style="overflow-x:auto;"><table class="data-table kis-ltable" id="secListTable"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
        '<p class="caption">분류 기준: ① 한기평(종합IB), 한신평(대형), NICE(대형IB) 중 한 곳이라도 대형으로 분류하면 대형, '
        '② 대형이 아닌 회사 중 한 곳이라도 중소형(한기평 일반증권사, 한신평 중소형, NICE 중형사·소형사)으로 분류하면 중소형이에요. '
        '자료: 3사 증권업 데이터(2026.2Q). 총자산·자기자본·ROA는 FISIS(업무보고서) 기준이고 ROA는 당기순이익(누계, 연환산) ÷ ((직전 결산말+해당 시점) 총자산 평균)이에요. '
        '신용등급은 3사 자료의 2026.06 기준 표기 그대로이고(한기평 장기(전망)/단기, 한신평 장기/전망, NICE 장기/전망 · 단기), 공시된 등급이 없으면 비워뒀어요. '
        'NICE는 NDB에 등급이 없어 NICE Market Comment 부록(증권업 신용등급 분포 및 추이)을 옮겨 적었고, [후]는 후순위사채 등급이에요.</p>'
    )


def render_bodies(prefix: str, quarters: list[str], list_html: str = "") -> list[str]:
    """TAB_LABELS 순서의 탭 본문."""
    ctl = render_controls()

    def sec(name):
        return f'<h4>{SECTION_TITLES[name]}</h4>' + _grid(prefix, SECTIONS[name])

    bodies = {
        "주요 지표": ctl + _tables("주요 지표") + _cbar(prefix, "cb_key", "회사별 지표 비교", CBAR_KEY, quarters) + sec("key"),
        "최근 실적": (ctl + _cbar(prefix, "cb_perf", "회사별 실적 비교", CBAR_PERF, quarters) + sec("perf_trend") + _ctable("회사별 최신 실적")),
        "수익성": ctl + _tables("수익성") + sec("pf"),
        "자산건전성": ctl + _tables("자산건전성") + sec("aq"),
        "자본적정성": ctl + _tables("자본적정성") + sec("cp"),
        "유동성": ctl + _tables("유동성") + sec("lq"),
        "파생결합증권": ctl + _tables("파생결합증권") + sec("dr"),
        "재무상태표": ctl + _tables("재무상태표") + sec("bs"),
        "손익계산서": ctl + _tables("손익계산서") + sec("is"),
        "전체 리스트": list_html,
    }
    return [bodies[t] for t in TAB_LABELS]


def render_data_script(payload: dict) -> str:
    return (f'<datalist class="kis-datalist" id="{LIST_ID}"></datalist>'
            f'<script type="application/json" class="kis-data" id="{DATA_ID}">'
            f'{json.dumps(payload, ensure_ascii=False, separators=(",", ":"))}</script>')
