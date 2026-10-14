"""증권사 페이지용 데이터: FISIS final_df(+ 엑셀 전용 항목)에서 회사 x 항목 x 분기 시계열을 만든다.

정의는 한국기업평가 증권업 재무자료(엑셀) '증권사비교' 시트/용어정의를 따랐고, 2026.06 기준으로 엑셀 값과
대조해 맞춘 것만 FISIS에서 직접 계산한다(verify_securities.py로 검증). FISIS에 없는 항목(영업순수익 구성,
수정NCR, 조정레버리지/유동성, 우발채무, ELS·DLS)은 data/securities_excel.json(엑셀에서 추출, 해당 시점만)을 쓴다.
금액은 억원, 손익은 당분기(누계 기준 비율은 분기 연율화).
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from dashboard.format import format_ym  # noqa: E402
from dashboard.loader import latest_final_df_path  # noqa: E402

SECTOR = "증권사"
START_YM = 201106       # '요약재무상태표/손익계산서(11.06월 이후)' 양식이 시작되는 시점
ALL_LABEL = "증권사 전체"
EXCEL_JSON = REPO_DIR / "data" / "securities_excel.json"

# (표시명, FISIS 금융회사코드, Peer 그룹, 결산월)  - 엑셀 용어정의의 Peer 그룹 기준(종합IB 9개사 / 일반증권사 16개사).
# '비교제외'(상상인증권)는 엑셀 비교표에 없어서 회사 선택은 되지만 업권 전체·Peer 합산에서는 뺀다.
CO_LIST = [
    ("미래에셋증권", 10094, "종합IB", 12), ("한국투자증권", 10129, "종합IB", 12), ("NH투자증권", 10101, "종합IB", 12),
    ("삼성증권", 10119, "종합IB", 12), ("KB증권", 10106, "종합IB", 12), ("하나증권", 10130, "종합IB", 12),
    ("신한투자증권", 10091, "종합IB", 12), ("키움증권", 10136, "종합IB", 12), ("대신증권", 10093, "종합IB", 12),
    ("교보증권", 10090, "일반증권사", 12), ("한화투자증권", 10110, "일반증권사", 12), ("신영증권", 10095, "일반증권사", 3),
    ("유안타증권", 10113, "일반증권사", 12), ("현대차증권", 10111, "일반증권사", 12), ("IBK투자증권", 12001, "일반증권사", 12),
    ("BNK투자증권", 12334, "일반증권사", 12), ("아이엠증권", 10128, "일반증권사", 12), ("유진투자증권", 10097, "일반증권사", 12),
    ("DB증권", 10120, "일반증권사", 12), ("엘에스증권", 10137, "일반증권사", 12), ("다올투자증권", 11981, "일반증권사", 12),
    ("SK증권", 10114, "일반증권사", 12), ("한양증권", 10098, "일반증권사", 12), ("디에스투자증권", 11980, "일반증권사", 12),
    ("케이프투자증권", 11978, "일반증권사", 12), ("상상인증권", 10104, "비교제외", 12), ("카카오페이증권", 11982, "일반증권사", 12),
]
GROUPS = ["종합IB", "일반증권사"]


def _calendar(first: str, last: str) -> list[str]:
    cal, y, m = [], int(first) // 100, int(first) % 100
    while y * 100 + m <= int(last):
        cal.append(f"{y * 100 + m:06d}")
        m += 3
        if m > 12:
            y, m = y + 1, m - 12
    return cal


def load_frame():
    path = latest_final_df_path(SECTOR)
    if path is None:
        return None
    df = pd.read_csv(path, index_col=0, encoding="cp949", low_memory=False)
    qcols = [c for c in df.columns if re.fullmatch(r"\d{6}", str(c)) and int(c) >= START_YM]
    codes = {code for _, code, _, _ in CO_LIST}
    df[qcols] = df[qcols].apply(pd.to_numeric, errors="coerce")
    all_df = df[(df["통계표코드"].astype(str) == "SF307") & (df["항목"] == "누계")]   # 업권 전체(외국계 지점 포함) 점유율 분모용
    df = df[df["금융회사코드"].isin(codes)].copy()
    return df, qcols, all_df


class SecData:
    """FISIS 행렬 접근 + 지표 계산. self.metrics = {키: {kind: sum|ratio, ...}}"""

    def __init__(self):
        got = load_frame()
        if got is None:
            raise RuntimeError("증권사 final_df가 없어요")
        self.df, qcols, self.df_all = got
        self.cal = _calendar(qcols[0], qcols[-1])
        self.cal_i = np.array([int(c) for c in self.cal])
        self.names = [n for n, *_ in CO_LIST]
        self.code_of = {c: n for n, c, _, _ in CO_LIST}
        self.group_of = {n: g for n, _, g, _ in CO_LIST}
        self.fye = {n: f for n, _, _, f in CO_LIST}
        self.qcols = qcols
        self._cache = {}
        self.metrics: dict[str, dict] = {}
        self._build()

    # ---- FISIS 행렬 (원 -> 억원)
    def g(self, table: str, code: str, item: str | None = None, scale: float = 1e8) -> pd.DataFrame:
        key = (table, code, item)
        if key not in self._cache:
            t = self.df[(self.df["통계표코드"].astype(str) == table) & (self.df["코드"] == code)]
            if item is not None:
                t = t[t["항목"] == item]
            m = t.groupby("금융회사코드")[self.qcols].first().rename(index=self.code_of)
            self._cache[key] = m.reindex(index=self.names, columns=self.cal)
        return self._cache[key] / scale

    def gs(self, table, codes, item=None):
        """여러 코드의 합(없는 값은 0으로 보되 전부 NaN이면 NaN)."""
        parts = [self.g(table, c, item) for c in codes]
        return sum(p.fillna(0) for p in parts).where(sum(p.notna().astype(int) for p in parts) > 0)

    def _months(self):
        """분기말 월 기준 결산월별 경과 개월(1~12)."""
        out = np.zeros((len(self.names), len(self.cal)))
        for i, n in enumerate(self.names):
            f = self.fye[n]
            for j, t in enumerate(self.cal_i):
                mm = t % 100
                k = (mm - f) % 12
                out[i, j] = 12 if k == 0 else k
        return pd.DataFrame(out, index=self.names, columns=self.cal)

    def _prev_fye(self, x: pd.DataFrame, months: pd.DataFrame) -> pd.DataFrame:
        """직전 결산 시점(= 해당 보고 시점에서 경과 개월만큼 이전 분기말) 값."""
        v, mo = x.to_numpy(), months.to_numpy()
        out = np.full(v.shape, np.nan)
        for j in range(v.shape[1]):
            src = j - (mo[:, j] / 3).astype(int)
            ok = src >= 0
            rows = np.where(ok)[0]
            out[rows, j] = v[rows, src[rows]]
        return pd.DataFrame(out, index=x.index, columns=x.columns)

    # ---- 지표
    def _build(self):
        g, gs = self.g, self.gs
        M = self.metrics
        months = self._months()
        ann = 12.0 / months

        def add_sum(key, d):
            M[key] = {"kind": "sum", "df": d}

        def add_ratio(key, num, den, mult=100.0):
            M[key] = {"kind": "ratio", "num": num, "den": den, "mult": mult}

        f0 = lambda x: x.fillna(0)

        # ================= 재무상태표 (SF303 자산 / SF304 부채·자본)
        A = lambda c: g("SF303", c, "금액")
        L = lambda c: g("SF304", c, "금액")
        asset = A("I")
        cash, dep, sec, deriv_a, loan = A("A01"), A("A02"), A("B"), A("C"), A("D")
        # 증권 구성 (측정범주별 보유현황 표를 유형별로 재분류)
        h1 = lambda c: g("SF017", c).fillna(0) + f0(g("SF018", c))   # 당기손익 + 기타포괄
        Zs = lambda x: x.where(sec.notna())
        sec_stock = h1("A1") + f0(h1("A2"))           # 주식 + 신주인수권증서/출자금
        sec_gov = h1("A3") + h1("A4") + f0(g("SF019", "A1")) + f0(g("SF019", "A2"))
        sec_cp = Zs(h1("A7"))
        sec_fund = Zs(h1("A6"))
        sec_fx = Zs(h1("A8"))
        sec_assoc = A("B04")
        sec_dlsec = A("B05")
        sec_etc = f0(h1("A9")) + f0(g("SF019", "A4"))
        sec_corp = sec - (f0(sec_stock) + f0(sec_gov) + f0(sec_cp) + f0(sec_fund) + f0(sec_fx) + f0(sec_assoc) + f0(sec_dlsec) + f0(sec_etc))
        # 대출채권 구성
        Z = lambda x, ref: x.fillna(0).where(ref.notna())   # 상위 항목이 있는 시점의 빈 하위 항목은 0
        ln_call = Z(f0(A("D01")) + f0(A("D03")), loan)
        ln_margin = Z(A("D02"), loan)
        ln_corp = sum(f0(A(c)) for c in ("D05", "D08", "D10", "D11", "D12", "D13", "D14", "D15"))   # 대출금+매입대출채권+부도채권·사모사채 등
        ln_jg = f0(A("D06")) + f0(A("D07"))
        ln_etc = f0(A("D04")) + f0(A("D09"))          # 대여금 + 대지급금
        ln_allow = loan - (f0(ln_call) + f0(ln_margin) + ln_corp + ln_jg + ln_etc)
        # 기타자산
        oth_a = asset - f0(cash) - f0(dep) - f0(sec) - f0(deriv_a) - f0(loan)
        oth_recv = A("H01")
        oth_allow = -A("H17")
        oth_etc = oth_a - f0(oth_recv) - f0(oth_allow)
        # 부채
        dep_l, dep_inv = L("A"), L("A01")
        borrow_real = sum(f0(L(c)) for c in ("B01", "B02", "B10", "B12", "B06", "B08"))
        lb = L("B")
        b_call, b_loan = Z(L("B01"), lb), Z(f0(L("B02")) + f0(L("B10")) + f0(L("B12")), lb)
        b_bond, b_sub = Z(L("B06"), lb), Z(L("B08"), lb)
        liab_tot = L("F")
        eq = L("L")
        ima = liab_tot - (f0(L("A")) + f0(L("B")) + f0(L("C")) + f0(L("D")) + f0(L("E")))
        ima = ima.where(ima.abs() >= 0.5, 0.0).where(liab_tot.notna())
        client_borrow = sum(f0(L(c)) for c in ("B03", "B04", "B05", "B11", "B13")) + f0(ima)
        add_sum("bs_cash", cash); add_sum("bs_dep", dep); add_sum("bs_sec", sec)
        add_sum("bs_sec_stock", sec_stock); add_sum("bs_sec_gov", sec_gov); add_sum("bs_sec_corp", sec_corp)
        add_sum("bs_sec_cp", sec_cp); add_sum("bs_sec_fund", sec_fund); add_sum("bs_sec_fx", sec_fx)
        add_sum("bs_sec_assoc", sec_assoc); add_sum("bs_sec_dlsec", sec_dlsec); add_sum("bs_sec_etc", sec_etc)
        add_sum("bs_deriv_a", deriv_a); add_sum("bs_loan", loan)
        add_sum("bs_ln_call", ln_call); add_sum("bs_ln_margin", ln_margin); add_sum("bs_ln_corp", ln_corp)
        add_sum("bs_ln_jg", ln_jg); add_sum("bs_ln_etc", ln_etc); add_sum("bs_ln_allow", ln_allow)
        add_sum("bs_oth_a", oth_a); add_sum("bs_oth_recv", oth_recv); add_sum("bs_oth_etc", oth_etc); add_sum("bs_oth_allow", oth_allow)
        add_sum("bs_sec_allow", sec * 0)              # 증권의 '대손충당금 등' (엑셀 양식 유지용, 항상 0)
        add_sum("bs_asset", asset)
        add_sum("bs_dep_l", dep_l); add_sum("bs_dep_inv", dep_inv)
        add_sum("bs_borrow_real", borrow_real); add_sum("bs_b_call", b_call); add_sum("bs_b_loan", b_loan)
        add_sum("bs_b_bond", b_bond); add_sum("bs_b_sub", b_sub)
        add_sum("bs_client", client_borrow)
        add_sum("bs_cb_rp", Z(L("B03"), lb)); add_sum("bs_cb_sec", Z(L("B04"), lb)); add_sum("bs_cb_dls", Z(L("B05"), lb))
        add_sum("bs_cb_note", Z(f0(L("B13")) + f0(L("B11")), lb)); add_sum("bs_cb_ima", ima)
        oth_l = L("D") + f0(L("E"))                   # 기타부채 = 기타부채 + 요구불상환지분(상환우선주 등)
        add_sum("bs_deriv_l", L("C")); add_sum("bs_oth_l", oth_l)
        add_sum("bs_oth_l_pay", L("D05")); add_sum("bs_oth_l_etc", oth_l - f0(L("D05")))
        add_sum("bs_liab", liab_tot); add_sum("bs_equity", eq); add_sum("bs_capital", L("G")); add_sum("bs_total", L("M"))

        # ================= 손익계산서 (SF307)
        def flow(code, kind="당분기"):
            return g("SF307", code, kind)

        def P(code):
            return flow(code, "당분기")

        def Y(code):
            return flow(code, "누계")

        def build_is(F):
            """F: 코드 -> 해당 기간(당분기/누계) 금액."""
            a5, a78, a79 = f0(F("A5")), f0(F("A78")), f0(F("A79"))
            rev = F("A") - a5 - a78 - a79
            b5, b805, b806 = f0(F("B5")), f0(F("B805")), f0(F("B806"))
            cost = F("B") - f0(F("B7")) - b5 - b805 - b806
            prov = b5 + b805 + b806 - a5 - a78 - a79
            return {
                "rev": rev, "r_fee": F("A1"), "r_sec": F("A2"), "r_der": F("A3"),
                "r_int": rev - f0(F("A1")) - f0(F("A2")) - f0(F("A3")),
                "cost": cost, "c_fee": F("B1"), "c_sec": F("B2"), "c_der": F("B3"),
                "c_int": cost - f0(F("B1")) - f0(F("B2")) - f0(F("B3")),
                "net": rev - cost, "prov": prov, "sga": F("B7"), "op": F("C"),
                "nonop_r": F("D"), "nonop_c": F("E"), "pretax": F("F"), "ni": F("J"),
            }
        IS_q, IS_y = build_is(P), build_is(Y)
        names_is = {"rev": "is_rev", "r_fee": "is_r_fee", "r_sec": "is_r_sec", "r_der": "is_r_der", "r_int": "is_r_int",
                    "cost": "is_cost", "c_fee": "is_c_fee", "c_sec": "is_c_sec", "c_der": "is_c_der", "c_int": "is_c_int",
                    "net": "is_net", "prov": "is_prov", "sga": "is_sga", "op": "is_op", "nonop_r": "is_nonop_r",
                    "nonop_c": "is_nonop_c", "pretax": "is_pretax", "ni": "is_ni"}
        for k, key in names_is.items():
            add_sum(key, IS_q[k])
        # 연도(12월) 열용: 최근 4개 분기 합계
        for k, key in names_is.items():
            add_sum(key + "_ltm", self._ltm(IS_q[k]))
        self.IS_q, self.IS_y = IS_q, IS_y

        # ================= 수익성 (엑셀 정의: 누계를 연환산 / (직전 결산말 + 당기말) 평균)
        avg_a = (asset + self._prev_fye(asset, months)) / 2
        avg_e = (eq + self._prev_fye(eq, months)) / 2
        add_ratio("pf_roa", IS_y["ni"] * ann, avg_a)
        add_ratio("pf_roe", IS_y["ni"] * ann, avg_e)
        add_ratio("pf_sga", IS_y["sga"], IS_y["net"])
        add_sum("pf_avg_a", avg_a)
        net_y = IS_y["net"]
        add_sum("is_net_ytd", net_y)
        # 영업순수익 점유율 분모 = FISIS 증권사 전체(외국계 지점 포함) 영업순수익(누계) 합계 (엑셀 정의)
        def _tot(code):
            t = self.df_all[self.df_all["코드"] == code].groupby("금융회사코드")[self.qcols].first()
            return t.sum(min_count=1).reindex(self.cal) / 1e8
        z0 = lambda x: x.fillna(0)
        net_all = ((_tot("A") - z0(_tot("A5")) - z0(_tot("A78")) - z0(_tot("A79")))
                   - (_tot("B") - z0(_tot("B7")) - z0(_tot("B5")) - z0(_tot("B805")) - z0(_tot("B806"))))
        M["pf_share"] = {"kind": "share", "df": net_y, "total": net_all}
        # 영업순수익 대비 비중 (참고)
        self.months, self.ann = months, ann

        # 총자산 대비 손익 구성 (분기 연율화, 분기 평잔은 직전 분기말 평균)
        avg_q = (asset + asset.shift(1, axis=1)) / 2
        q_ann = 4.0
        add_ratio("dc_fee", (f0(IS_q["r_fee"]) - f0(IS_q["c_fee"])) * q_ann, avg_q)
        add_ratio("dc_sec", (f0(IS_q["r_sec"]) - f0(IS_q["c_sec"])) * q_ann, avg_q)
        add_ratio("dc_der", (f0(IS_q["r_der"]) - f0(IS_q["c_der"])) * q_ann, avg_q)
        add_ratio("dc_int", (f0(IS_q["r_int"]) - f0(IS_q["c_int"])) * q_ann, avg_q)
        add_ratio("dc_sga", -f0(IS_q["sga"]) * q_ann, avg_q)
        add_ratio("dc_prov", -f0(IS_q["prov"]) * q_ann, avg_q)
        add_ratio("dc_roa_q", IS_q["ni"] * q_ann, avg_q)
        asset4 = asset.shift(4, axis=1)
        add_ratio("bs_asset_yoy", asset - asset4, asset4)
        ni4 = self._ltm(IS_q["ni"])
        add_ratio("pf_roa_ltm", ni4, (asset.T.rolling(5, min_periods=5).mean().T))

        # ================= 자산건전성 (SF311 V '계')
        def Vt(item):
            return g("SF311", "V", item)
        total_ast = Vt("합계")
        below = f0(Vt("고정")) + f0(Vt("회수의문")) + f0(Vt("추정손실"))
        below = below.where(total_ast.notna())
        watch = f0(Vt("요주의")) + below
        watch = watch.where(total_ast.notna())
        allow = f0(A("D16")) + f0(A("H17")) + f0(A("B06"))
        allow = allow.where(asset.notna())
        add_sum("aq_total", total_ast); add_sum("aq_watch", watch); add_sum("aq_sub", below); add_sum("aq_allow", allow)
        add_ratio("aq_watch_r", watch, total_ast)
        add_ratio("aq_sub_r", below, total_ast)
        add_ratio("aq_nwatch", watch - allow, eq)
        add_ratio("aq_nsub", below - allow, eq)
        add_ratio("aq_cov", allow, below)

        # ================= 자본적정성 (연결기준 순자본비율 SF408 2016.03~, 개별기준 SF308 2015.03~)
        ncap = g("SF408", "A").combine_first(g("SF308", "A"))
        risk = g("SF408", "B").combine_first(g("SF308", "B"))
        req = g("SF408", "D").combine_first(g("SF308", "D"))
        add_sum("cp_ncap", ncap); add_sum("cp_risk", risk); add_sum("cp_req", req)
        add_ratio("cp_ncr", ncap - risk, req)
        lev_a, lev_e = g("SF331", "A"), g("SF331", "B")
        add_ratio("cp_lev", lev_a, lev_e, mult=1.0)
        add_sum("cp_lev_a", lev_a); add_sum("cp_lev_e", lev_e)

        # ================= 유동성 (SF209)
        la, lb = g("SF209", "A"), g("SF209", "B")
        add_sum("lq_assets", la); add_sum("lq_liab", lb); add_sum("lq_gap", la - lb)
        add_ratio("lq_ratio", la, lb)

        # ================= 파생결합증권 (FISIS: 재무상태표상 잔액)
        add_sum("dr_asset", sec_dlsec); add_sum("dr_sold", L("B05"))

        self._excel_metrics(eq, la - lb)

    def _ltm(self, flow: pd.DataFrame) -> pd.DataFrame:
        """최근 4개 분기 합(4개 모두 값이 있을 때만)."""
        f = flow.to_numpy()
        out = np.full(f.shape, np.nan)
        for j in range(3, f.shape[1]):
            w = f[:, j - 3:j + 1]
            ok = ~np.isnan(w).any(axis=1)
            out[ok, j] = w[ok].sum(axis=1)
        return pd.DataFrame(out, index=flow.index, columns=flow.columns)

    # ---- 엑셀 전용 항목 (FISIS에 없음): 해당 시점에만 값이 있음
    def _excel_metrics(self, eq: pd.DataFrame, gap: pd.DataFrame):
        M = self.metrics

        def blank():
            return pd.DataFrame(np.nan, index=self.names, columns=self.cal)

        ex = {}
        self.excel_periods = []
        if EXCEL_JSON.exists():
            raw = json.loads(EXCEL_JSON.read_text(encoding="utf-8"))
            self.excel_periods = raw["periods"]
            keys = {k for per in raw["data"].values() for co in per.values() for k in co}
            for k in keys:
                ex[k] = blank()
            for ym, per in raw["data"].items():
                if ym not in self.cal:
                    continue
                for co, vals in per.items():
                    if co not in self.names:
                        continue
                    for k, v in vals.items():
                        ex[k].loc[co, ym] = v
        for k, d in ex.items():
            # 비율형 엑셀 값(합산 불가)은 회사별로만 쓰고 업권/Peer 합산 시계열은 만들지 않는다
            M[k] = {"kind": "company" if k in ("ex_adj_liq", "ex_cont_gap", "ex_adj_lev", "ex_adj_ncr", "ex_hedge_eq", "ex_hedge_gap", "ex_cont_eq") else "sum", "df": d}
        if not ex:
            return
        z = blank()
        for k in ("ex_brokerage", "ex_trading", "ex_ib", "ex_wm", "ex_otherrev", "ex_adj_ncap", "ex_adj_risk", "ex_els", "ex_dls", "ex_hedge", "ex_cont"):
            ex.setdefault(k, z)
        M["ex_adj_ncr"] = {"kind": "ratio", "num": ex["ex_adj_ncap"], "den": ex["ex_adj_risk"], "mult": 100.0}
        M["ex_hedge_eq"] = {"kind": "ratio", "num": ex["ex_hedge"], "den": eq, "mult": 100.0}
        M["ex_hedge_gap"] = {"kind": "ratio", "num": ex["ex_hedge"], "den": gap, "mult": 100.0}
        M["ex_cont_eq"] = {"kind": "ratio", "num": ex["ex_cont"], "den": eq, "mult": 100.0}
        # 조정레버리지배율 = 조정자산/자기자본 -> 업권 합산은 자기자본 가중평균
        if "ex_adj_lev" in ex:
            M["ex_adj_lev"] = {"kind": "ratio", "num": ex["ex_adj_lev"] * eq, "den": eq.where(ex["ex_adj_lev"].notna()), "mult": 1.0}
        # 영업순수익 구성 비중 (구성 합계 대비)
        tot = ex["ex_brokerage"] + ex["ex_trading"] + ex["ex_ib"] + ex["ex_wm"] + ex["ex_otherrev"]
        for k in ("brokerage", "trading", "ib", "wm", "otherrev"):
            M[f"ex_{k}_sh"] = {"kind": "ratio", "num": ex[f"ex_{k}"], "den": tot, "mult": 100.0}
        M["ex_net_total"] = {"kind": "sum", "df": tot}

    # ---- 회사 / 업권 / Peer 시계열
    def payload(self) -> dict:
        names = self.names
        grp = {g_: [n for n in names if self.group_of[n] == g_] for g_ in GROUPS}
        agg_names = [n for n in names if self.group_of[n] in GROUPS]   # 업권 전체 = 엑셀 비교 대상 회사
        series: dict[str, dict] = {c: {} for c in names + [ALL_LABEL] + GROUPS}

        def to_list(row):
            return [None if (v is None or not np.isfinite(v)) else round(float(v), 3) for v in row]

        for key, m in self.metrics.items():
            kind = m["kind"]
            if kind == "company":
                per, aggs = m["df"].reindex(names), {}
            elif kind == "sum":
                per = m["df"].reindex(names)
                aggs = {ALL_LABEL: per.loc[agg_names].sum(min_count=1)}
                for g_, cs in grp.items():
                    aggs[g_] = per.loc[cs].sum(min_count=1)
            elif kind == "share":   # 업권 합계 대비 점유율(%)
                per0 = m["df"].reindex(names)
                tot = m["total"]
                per = per0.div(tot, axis=1) * 100
                aggs = {}
                for g_, cs in grp.items():
                    aggs[g_] = per0.loc[cs].sum(min_count=1) / tot * 100
                aggs[ALL_LABEL] = per0.loc[agg_names].sum(min_count=1) / tot * 100
            else:
                num, den = m["num"].reindex(names), m["den"].reindex(names)
                ok = num.notna() & den.notna() & (den != 0)
                per = (num / den.where(den != 0)) * m["mult"]
                aggs = {ALL_LABEL: (num.loc[agg_names].where(ok.loc[agg_names]).sum(min_count=1)
                                    / den.loc[agg_names].where(ok.loc[agg_names]).sum(min_count=1) * m["mult"])}
                for g_, cs in grp.items():
                    aggs[g_] = (num.loc[cs].where(ok.loc[cs]).sum(min_count=1)
                                / den.loc[cs].where(ok.loc[cs]).sum(min_count=1) * m["mult"])
            for c in names:
                vals = to_list(per.loc[c].to_numpy())
                if any(v is not None for v in vals):
                    series[c][key] = vals
            for lab, agg in aggs.items():
                vals = to_list(agg.to_numpy())
                if any(v is not None for v in vals):
                    series[lab][key] = vals

        asset_latest = self.metrics["bs_asset"]["df"][self.cal[-1]].fillna(0)
        companies_sorted = sorted(names, key=lambda c: -asset_latest.get(c, 0))
        return {
            "quarters": [format_ym(int(q)) for q in self.cal],
            "allLabel": ALL_LABEL,
            "groups": GROUPS,
            "ratedLabel": "",
            "companies": [ALL_LABEL] + companies_sorted,
            "rated": [ALL_LABEL] + companies_sorted,
            "series": {k: v for k, v in series.items() if v},
            "excelQuarters": [format_ym(int(q)) for q in self.excel_periods],
        }


def build_sec_payload() -> dict | None:
    if latest_final_df_path(SECTOR) is None:
        return None
    return SecData().payload()


if __name__ == "__main__":
    p = build_sec_payload()
    print(len(p["quarters"]), p["quarters"][0], p["quarters"][-1], len(p["series"]), len(p["companies"]))
