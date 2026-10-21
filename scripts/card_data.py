"""신용카드사 페이지용 데이터: FISIS final_df에서 회사 x 항목 x 분기 시계열을 만든다.

항목 구성은 3사(한기평 Data Sheet / 한신평 Data Package / NICE NDB) 신용카드 자료의 합집합을 따르되, 숫자는 전부 FISIS(업무보고서)에서 계산한다.
금액은 억원, 손익은 당분기(누계는 같은 해 직전 분기 누계와 차분해서 만든다 - 2018.12 전후로 손익계산서 통계표가 SC118/SC218로 나뉘어도 이어짐).
정의 메모(2026.06 한기평 엑셀과 대조):
  * 영업수익 = 수익합계 - 대손충당금 환입 등(B67+B68+B81), 영업비용 = 비용합계 - 대손상각비 등(D69+D6A+D6C+D91)
  * PPOP = 영업수익 - 영업비용, 대손비용 = 대손상각비 등 - 환입 등, 영업이익 = PPOP - 대손비용 (= 세전이익; FISIS에는 영업외손익 구분이 없음)
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from dashboard.format import format_ym  # noqa: E402
from dashboard.loader import latest_final_df_path  # noqa: E402

SECTOR = "신용카드사"
START_YM = 201103
ALL_LABEL = "카드사 전체"      # 전업카드사 7개(BC카드 제외 - 3사 자료도 같은 범위)
# (표시명, FISIS 금융회사코드, 합산 포함 여부)
CO_LIST = [
    ("신한카드", 10229, True), ("삼성카드", 10228, True), ("KB국민카드", 12627, True), ("현대카드", 10225, True),
    ("롯데카드", 10226, True), ("우리카드", 13361, True), ("하나카드", 13640, True), ("BC카드", 10227, False),
]


def _calendar(first: str, last: str) -> list[str]:
    cal, y, m = [], int(first) // 100, int(first) % 100
    while y * 100 + m <= int(last):
        cal.append(f"{y * 100 + m:06d}")
        m += 3
        if m > 12:
            y, m = y + 1, m - 12
    return cal


class CardData:
    def __init__(self):
        path = latest_final_df_path(SECTOR)
        if path is None:
            raise RuntimeError("신용카드사 final_df가 없어요")
        df = pd.read_csv(path, index_col=0, encoding="cp949", low_memory=False)
        self.qcols = [c for c in df.columns if re.fullmatch(r"\d{6}", str(c)) and int(c) >= START_YM]
        codes = {c for _, c, _ in CO_LIST}
        self.df = df[df["금융회사코드"].isin(codes)].copy()
        self.df[self.qcols] = self.df[self.qcols].apply(pd.to_numeric, errors="coerce")
        self.cal = _calendar(self.qcols[0], self.qcols[-1])
        self.cal_i = np.array([int(c) for c in self.cal])
        self.names = [n for n, _, _ in CO_LIST]
        self.code_of = {c: n for n, c, _ in CO_LIST}
        self.in_agg = {n: a for n, _, a in CO_LIST}
        self._cache: dict = {}
        self.metrics: dict[str, dict] = {}
        self._build()

    # ---- FISIS 행렬 (원 -> 억원)
    def g(self, table, code, item=None, scale=1e8):
        key = (table, code, item)
        if key not in self._cache:
            t = self.df[(self.df["통계표코드"].astype(str) == table) & (self.df["코드"] == code)]
            if item is not None:
                t = t[t["항목"] == item]
            m = t.groupby("금융회사코드")[self.qcols].first().rename(index=self.code_of)
            self._cache[key] = m.reindex(index=self.names, columns=self.cal)
        return self._cache[key] / scale

    def cum(self, code):
        """손익계산서 누계(연초~해당 분기): 2018.09까지 SC118, 2018.12부터 SC218."""
        return self.g("SC118", code, "누계").combine_first(self.g("SC218", code, "누계"))

    def _flow(self, cumdf):
        """누계 -> 당분기 (1분기는 누계, 그 외는 직전 분기 누계와의 차)."""
        v = cumdf.to_numpy()
        out = np.full(v.shape, np.nan)
        for j, t in enumerate(self.cal_i):
            if t % 100 == 3:
                out[:, j] = v[:, j]
            elif j > 0:
                out[:, j] = v[:, j] - v[:, j - 1]
        return pd.DataFrame(out, index=cumdf.index, columns=cumdf.columns)

    def _ltm(self, flow):
        f = flow.to_numpy()
        out = np.full(f.shape, np.nan)
        for j in range(3, f.shape[1]):
            w = f[:, j - 3:j + 1]
            ok = ~np.isnan(w).any(axis=1)
            out[ok, j] = w[ok].sum(axis=1)
        return pd.DataFrame(out, index=flow.index, columns=flow.columns)

    def _months(self):
        mo = np.array([(t % 100) for t in self.cal_i], dtype=float)
        return pd.DataFrame(np.tile(mo, (len(self.names), 1)), index=self.names, columns=self.cal)

    def _prev_fye(self, x, months):
        v, mo = x.to_numpy(), months.to_numpy()
        out = np.full(v.shape, np.nan)
        for j in range(v.shape[1]):
            src = j - (mo[:, j] / 3).astype(int)
            ok = src >= 0
            rows = np.where(ok)[0]
            out[rows, j] = v[rows, src[rows]]
        return pd.DataFrame(out, index=x.index, columns=x.columns)

    def _build(self):
        g, M = self.g, self.metrics
        f0 = lambda x: x.fillna(0)

        def add_sum(key, d):
            M[key] = {"kind": "sum", "df": d}

        def add_ratio(key, num, den, mult=100.0):
            M[key] = {"kind": "ratio", "num": num, "den": den, "mult": mult}

        # ================= 재무상태표 (SC103 자산 / SC104 부채·자본)
        A = lambda c: g("SC103", c, "금액")
        L = lambda c: g("SC104", c, "금액")
        asset = A("A")
        cashdep, sec, loan, card, inst, lease, nbt = A("A1"), A("A2"), A("A3"), A("A4"), A("A5"), A("A6"), A("A7")
        ops = f0(card) + f0(inst) + f0(lease) + f0(loan) + f0(nbt)
        ops = ops.where(asset.notna())
        oth_a = asset - f0(cashdep) - f0(sec) - ops
        borrow, b_loan, bond = L("A11"), L("A110"), L("A115")
        liab, eq = L("A1"), L("A2")
        for k, v in (("bs_cashdep", cashdep), ("bs_sec", sec), ("bs_ops", ops), ("bs_card", card), ("bs_inst", inst), ("bs_lease", lease),
                     ("bs_loan", loan), ("bs_nbt", nbt), ("bs_oth_a", oth_a), ("bs_asset", asset), ("bs_borrow", borrow),
                     ("bs_b_loan", b_loan), ("bs_bond", bond), ("bs_pay", L("A120")), ("bs_unused", L("A12C")), ("bs_liab", liab),
                     ("bs_capital", L("A21")), ("bs_equity", eq),
                     ("bs_oth_l", liab - f0(borrow)), ("bs_loan_nbt", f0(loan) + f0(nbt))):
            add_sum(k, v)
        add_ratio("bs_ops_yoy", ops - ops.shift(4, axis=1), ops.shift(4, axis=1))     # 영업자산 증감률(전년 동기 대비)
        add_ratio("bs_lev", asset, eq, mult=1.0)                                      # 총자산/자기자본(배)

        # ================= 손익계산서 (누계 -> 당분기)
        C = self.cum
        reversal = f0(C("B67")) + f0(C("B68")) + f0(C("B81"))
        dae_gross = f0(C("D69")) + f0(C("D6A")) + f0(C("D6C")) + f0(C("D91"))
        has = C("A").notna()
        rev = (C("A") - reversal)
        cost = (C("C") - dae_gross)
        comp_r = {"r_card": C("B2"), "r_inst": C("B3"), "r_lease": C("B4"), "r_loanint": C("B12"), "r_nbt": C("B5"), "r_sec": C("B7")}
        comp_c = {"c_int": C("D1"), "c_card": C("D2"), "c_inst": C("D7"), "c_lease": C("D3"), "c_nbt": C("D4"), "c_sga": C("D5"), "c_sec": C("D8")}
        IS_y = {"rev": rev, "cost": cost, "ppop": rev - cost, "dae": dae_gross - reversal, "dae_gross": dae_gross, "reversal": reversal,
                "pretax": C("H"), "ni": C("J")}
        IS_y["op"] = IS_y["ppop"] - IS_y["dae"]
        IS_y.update(comp_r)
        IS_y.update(comp_c)
        IS_y["r_oth"] = rev - sum(f0(v) for v in comp_r.values())
        IS_y["c_oth"] = cost - sum(f0(v) for v in comp_c.values())
        # 카드수익 구성
        IS_y.update({"cr_fee": C("B20"), "cr_inst": C("B23"), "cr_cash": C("B24"), "cr_loan": C("B25"), "cr_annual": C("B26")})
        IS_y["cr_oth"] = C("B2") - sum(f0(IS_y[k]) for k in ("cr_fee", "cr_inst", "cr_cash", "cr_loan", "cr_annual"))
        IS_q = {k: self._flow(v) for k, v in IS_y.items()}
        # 2018.12부터 손익계산서 통계표(SC218)의 수익·비용 표시 기준이 바뀌어(총액 -> 순액 등) 2018.Q4 분기 금액이 이어지지 않는다. 비교 가능한 항목(PPOP·대손·순이익 등)만 남기고 비움.
        keep = {"ni", "pretax", "dae", "dae_gross", "reversal", "ppop", "op"}
        for k, v in IS_q.items():
            if k not in keep and "201812" in v.columns:
                v["201812"] = np.nan
        self.IS_y, self.IS_q = IS_y, IS_q
        for k in IS_y:
            add_sum(f"is_{k}", IS_q[k])
            add_sum(f"is_{k}_ltm", self._ltm(IS_q[k]))
            add_sum(f"is_{k}_ytd", IS_y[k])

        # ================= 수익성 (엑셀 정의: 누계 연환산 / (직전 결산말+당기말) 평균 자산)
        months = self._months()
        ann = 12.0 / months
        avg_a = (asset + self._prev_fye(asset, months)) / 2
        avg_e = (eq + self._prev_fye(eq, months)) / 2
        add_ratio("pf_roa", IS_y["ni"] * ann, avg_a)
        add_ratio("pf_roe", IS_y["ni"] * ann, avg_e)
        add_ratio("pf_ppop", IS_y["ppop"] * ann, avg_a)
        add_ratio("pf_dae", IS_y["dae"] * ann, avg_a)
        add_ratio("pf_op", IS_y["op"] * ann, avg_a)
        add_ratio("pf_sga", IS_y["c_sga"], IS_y["rev"])                              # 판관비율(영업수익 대비)
        add_ratio("pf_cardshare", IS_y["r_card"], IS_y["rev"])                        # 카드수익 비중
        # 분기 개별(연율화) / 4분기 누적
        avg_q = (asset + asset.shift(1, axis=1)) / 2
        avg_eq_q = (eq + eq.shift(1, axis=1)) / 2
        add_ratio("pf_roa_q", IS_q["ni"] * 4, avg_q)
        add_ratio("pf_roe_q", IS_q["ni"] * 4, avg_eq_q)
        add_ratio("pf_ppop_q", IS_q["ppop"] * 4, avg_q)
        add_ratio("pf_dae_q", IS_q["dae"] * 4, avg_q)
        add_ratio("pf_op_q", IS_q["op"] * 4, avg_q)
        asset5 = asset.T.rolling(5, min_periods=5).mean().T
        add_ratio("pf_roa_4", self._ltm(IS_q["ni"]), asset5)
        add_ratio("pf_ppop_4", self._ltm(IS_q["ppop"]), asset5)
        add_ratio("pf_dae_4", self._ltm(IS_q["dae"]), asset5)

        # ================= 자산건전성 (SC008 여신건전성, SC117 연체채권비율)
        tot = g("SC008", "A")
        sub = g("SC008", "A4")
        need, allow = g("SC008", "B"), g("SC008", "C")
        over = g("SC117", "A5")
        add_sum("aq_total", tot); add_sum("aq_sub", sub); add_sum("aq_need", need); add_sum("aq_allow", allow); add_sum("aq_over", over)
        add_ratio("aq_subr", sub, tot)
        add_ratio("aq_overr", over, g("SC117", "A"))
        # 연체채권(1개월 이상, 대환대출 포함 = 금감원 기준): FISIS는 비율(소수 둘째 자리까지)만 공시해서 비율 x 총채권으로 역산 (금액 오차 약 +-20억원)
        ratio2 = g("SC117", "C", None, 1.0)
        ratio2 = ratio2.where((ratio2 >= 0) & (ratio2 <= 100))      # FISIS 원자료 오류(KB국민카드 2011.Q1 = 14,315,200) 제외
        over2 = ratio2 / 100 * g("SC117", "A")
        add_sum("aq_over2", over2)
        add_ratio("aq_overr2", over2, g("SC117", "A"))
        add_ratio("aq_cov", allow, sub)                                                              # 대손충당금/고정이하여신
        add_ratio("aq_covover", allow, over)                                                         # 대손충당금/연체채권(1개월 이상)
        add_ratio("aq_covneed", allow, need)                                                         # 대손충당금 적립비율(요적립액 대비)

        # ================= 자본적정성 (SC007)
        add_sum("cp_adj_cap", g("SC007", "A1")); add_sum("cp_adj_asset", g("SC007", "A2"))
        add_ratio("cp_adjr", g("SC007", "A1"), g("SC007", "A2"))
        add_ratio("cp_simple", g("SC007", "B1"), g("SC007", "B2"))
        M["cp_lev"] = M["bs_lev"]

        # ================= 유동성 / 자금조달 (SC010, SC005)
        add_sum("lq_assets", g("SC010", "A1")); add_sum("lq_liab", g("SC010", "A2"))
        add_ratio("lq_ratio", g("SC010", "A1"), g("SC010", "A2"))
        add_ratio("lq_instant", g("SC010", "C1"), g("SC010", "C2"))
        add_ratio("lq_short", g("SC010", "D1"), g("SC010", "D2"))
        fund = g("SC005", "A", "금액")
        for k, c in (("fd_loan", "A1"), ("fd_bond", "A2"), ("fd_abs", "A4")):
            add_sum(k, g("SC005", c, "금액"))
        add_sum("fd_total", fund)
        add_sum("fd_other", fund - f0(g("SC005", "A1", "금액")) - f0(g("SC005", "A2", "금액")) - f0(g("SC005", "A4", "금액")))
        add_ratio("fd_bondr", g("SC005", "A2", "금액"), fund)

        # ================= 이용실적 (SC013 신용카드, SC014 체크, SC015 선불) - 당분기
        U = lambda c: g("SC013", c, "당분기")
        for k, c in (("us_lump", "D1"), ("us_inst", "D2"), ("us_cash", "D3"), ("us_loan", "D4"), ("us_total", "D5")):
            add_sum(k, U(c))
        add_sum("us_check", g("SC014", "A3", "당분기")); add_sum("us_prepaid", g("SC015", "A1", "당분기"))
        add_sum("us_pers", U("A5")); add_sum("us_corp", U("B5")); add_sum("us_buyonly", U("C3"))
        add_ratio("us_loanshare", f0(U("D3")) + f0(U("D4")), U("D5"))        # 카드대출 비중(현금서비스+카드론)
        add_ratio("us_loanonly", U("D4"), U("D5"))                           # 카드론 비중
        add_ratio("us_instshare", U("D2"), U("D5"))                          # 할부 비중
        for k in [k for k, m in list(M.items()) if k.startswith("us_") and m["kind"] == "sum"]:
            add_sum(k + "_ltm", self._ltm(M[k]["df"]))                       # 연도(12월) 열용: 최근 4개 분기 합

    # ---- 회사 / 합산 시계열
    def payload(self) -> dict:
        names = self.names
        agg_names = [n for n in names if self.in_agg[n]]
        series: dict[str, dict] = {c: {} for c in names + [ALL_LABEL]}

        def to_list(row):
            return [None if (v is None or not np.isfinite(v)) else round(float(v), 3) for v in row]

        for key, m in self.metrics.items():
            if m["kind"] == "sum":
                per = m["df"].reindex(names)
                agg = per.loc[agg_names].sum(min_count=1)
            else:
                num, den = m["num"].reindex(names), m["den"].reindex(names)
                ok = num.notna() & den.notna() & (den != 0)
                per = (num / den.where(den != 0)) * m["mult"]
                agg = (num.loc[agg_names].where(ok.loc[agg_names]).sum(min_count=1)
                       / den.loc[agg_names].where(ok.loc[agg_names]).sum(min_count=1) * m["mult"])
            for c in names:
                vals = to_list(per.loc[c].to_numpy())
                if any(v is not None for v in vals):
                    series[c][key] = vals
            vals = to_list(agg.to_numpy())
            if any(v is not None for v in vals):
                series[ALL_LABEL][key] = vals

        asset_latest = self.metrics["bs_asset"]["df"][self.cal[-1]].fillna(0)
        companies_sorted = sorted([n for n in names if asset_latest.get(n, 0) > 0], key=lambda c: -asset_latest.get(c, 0))
        return {
            "quarters": [format_ym(int(q)) for q in self.cal],
            "allLabel": ALL_LABEL,
            "groups": [],
            "ratedLabel": "",
            "companies": [ALL_LABEL] + companies_sorted,
            "rated": [ALL_LABEL] + companies_sorted,
            "series": {k: v for k, v in series.items() if v},
        }


def build_list_rows():
    """FISIS 카드사(8개)의 총자산·자기자본·ROA (전체 리스트 탭용)."""
    cd = CardData()
    last = cd.cal[-1]

    def val(key):
        m = cd.metrics[key]
        if m["kind"] == "sum":
            return m["df"][last]
        return m["num"][last] / m["den"][last].where(m["den"][last] != 0) * m["mult"]

    asset, eq, roa = val("bs_asset"), val("bs_equity"), val("pf_roa")
    pick = lambda x: None if x is None or not np.isfinite(x) else float(x)
    rows = [{"name": n, "asset": pick(asset.get(n)), "equity": pick(eq.get(n)), "roa": pick(roa.get(n))}
            for n in cd.names if pick(asset.get(n))]
    return rows, format_ym(int(last))


def build_card_payload() -> dict | None:
    if latest_final_df_path(SECTOR) is None:
        return None
    return CardData().payload()


if __name__ == "__main__":
    p = build_card_payload()
    print(len(p["quarters"]), p["quarters"][0], p["quarters"][-1], len(p["series"]), p["companies"])
