"""부동산신탁 페이지용 데이터: FISIS final_df에서 회사 x 항목 x 분기 시계열을 만든다.

항목 구성은 신평사(한기평 Data Sheet / NICE NDB) 부동산신탁 자료의 합집합을 따르되, 숫자는 전부 FISIS(업무보고서)에서 계산한다.
금액은 억원, 손익은 당분기(누계는 같은 해 직전 분기 누계와 차분해서 만든다 - 2011.Q1 전후로 통계표가 SM034/SM007로 나뉘어도 이어짐).
정의 메모(2026.06 한기평 엑셀·NICE NDB와 대조):
  * 영업수익 = 영업수익 - 충당금 환입(A52+A53+A62), 영업비용 = 영업비용 - 대손상각비 등(B7+B61) - 충당금전입액(B60)
  * PPOP = 영업수익 - 영업비용, 대손비용 = (B7+B61) - (A53+A62), 기타충당금적립 = B60 - A52, 영업이익 = PPOP - 대손비용 - 기타충당금적립 (= FISIS 영업이익)
  * 대손충당금(총) = 대출채권 대손충당금 + 기타자산 대손충당금, 신탁계정대 충당금 = 신탁계정대 대손충당금
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

SECTOR = "부동산신탁"
START_YM = 200903
ALL_LABEL = "부동산신탁 전체"      # FISIS 부동산신탁사 14개 합산 (2019.Q3~ 대신, 2019.Q4~ 한국투자·신영이 들어와 합산 규모가 늘어남)
# (표시명, FISIS 금융회사코드)
CO_LIST = [
    ("한국토지신탁", 10902), ("KB부동산신탁", 10903), ("대한토지신탁", 10904), ("교보자산신탁", 10905), ("한국자산신탁", 10906),
    ("하나자산신탁", 11452), ("코람코자산신탁", 11643), ("신한자산신탁", 11877), ("우리자산신탁", 11892), ("무궁화신탁", 12279),
    ("코리아신탁", 12306), ("대신자산신탁", 16953), ("한국투자부동산신탁", 17106), ("신영부동산신탁", 17107),
]


def _calendar(first: str, last: str) -> list[str]:
    cal, y, m = [], int(first) // 100, int(first) % 100
    while y * 100 + m <= int(last):
        cal.append(f"{y * 100 + m:06d}")
        m += 3
        if m > 12:
            y, m = y + 1, m - 12
    return cal


class TrustData:
    def __init__(self):
        path = latest_final_df_path(SECTOR)
        if path is None:
            raise RuntimeError("부동산신탁 final_df가 없어요")
        df = pd.read_csv(path, index_col=0, encoding="cp949", low_memory=False)
        self.qcols = [c for c in df.columns if re.fullmatch(r"\d{6}", str(c)) and int(c) >= START_YM]
        codes = {c for _, c in CO_LIST}
        self.df = df[df["금융회사코드"].isin(codes)].copy()
        self.df[self.qcols] = self.df[self.qcols].apply(pd.to_numeric, errors="coerce")
        self.cal = _calendar(self.qcols[0], self.qcols[-1])
        self.cal_i = np.array([int(c) for c in self.cal])
        self.names = [n for n, _ in CO_LIST]
        self.code_of = {c: n for n, c in CO_LIST}
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

    def bs(self, code):
        """재무상태표: 2011.Q2~ SM005, 그 전은 SM033."""
        return self.g("SM005", code, "금액").combine_first(self.g("SM033", code, "금액"))

    def cum(self, code):
        """손익계산서 누계(연초~해당 분기): 2011.Q1~ SM007, 그 전은 SM034."""
        return self.g("SM007", code, "누계").combine_first(self.g("SM034", code, "누계"))

    def _flow(self, cumdf):
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

        def add_share(key, d):
            """회사별 점유율(%) = 회사 값 / 전체 회사 합. 합산 선은 의미가 없어서 만들지 않는다."""
            M[key] = {"kind": "share", "df": d.div(d.sum(axis=0, min_count=1), axis=1) * 100}

        # ================= 재무상태표 (SM005 / SM033)
        B = self.bs
        asset, cashdep, sec, loan, tang = B("A"), B("A1"), B("A2"), B("A4"), B("A5")
        oth_a = asset - f0(cashdep) - f0(sec) - f0(loan) - f0(tang)
        borrow, liab, eq, capital = B("B2"), B("B"), B("C"), B("C1")
        b_loan, bond = g("SM005", "B22", "금액"), g("SM005", "B24", "금액")
        tl, tl_allow = g("SM005", "A45", "금액"), g("SM005", "A472", "금액")
        allow_tot = g("SM005", "A47", "금액") + f0(g("SM005", "A8G", "금액"))
        for k, v in (("bs_asset", asset), ("bs_cashdep", cashdep), ("bs_sec", sec), ("bs_loan", loan), ("bs_tang", tang), ("bs_oth_a", oth_a),
                     ("bs_borrow", borrow), ("bs_b_loan", b_loan), ("bs_bond", bond), ("bs_liab", liab), ("bs_capital", capital), ("bs_equity", eq),
                     ("bs_oth_l", liab - f0(borrow)), ("bs_tl", tl), ("bs_tl_allow", tl_allow), ("bs_tl_net", tl - tl_allow),
                     ("bs_allow_tot", allow_tot)):
            add_sum(k, v)
        add_sum("bs_loan_other", loan - (tl - tl_allow))
        add_ratio("bs_lev", asset, eq, mult=1.0)                         # 총자산/자기자본(배)
        add_ratio("bs_dr", liab, eq)                                      # 부채비율
        add_ratio("bs_borrowr", borrow, asset)                            # 차입금의존도
        add_ratio("bs_netborrowr", borrow - cashdep, asset)               # 순차입금의존도 = (차입부채 - 현금및예치금) / 총자산
        add_ratio("bs_cashr", cashdep, asset)
        add_ratio("bs_bondr", bond, borrow)                               # 차입부채 중 사채 비중
        add_ratio("bs_tl_eq", tl - tl_allow, eq)                          # 신탁계정대(순)/자기자본
        add_ratio("bs_tl_ar", tl_allow, tl)                               # 신탁계정대 충당금/신탁계정대
        add_ratio("bs_tl_asset", tl - tl_allow, asset)                    # 신탁계정대(순)/총자산
        add_share("ms_asset", asset)

        # ================= 손익계산서 (누계 -> 당분기)
        C = self.cum
        rev_raw = C("A")
        reversal = f0(C("A53")) + f0(C("A62"))                            # 대손충당금 환입(대출채권·기타)
        a52 = f0(C("A52"))                                                # 충당금환입액
        rev = rev_raw - a52 - reversal
        dae_gross = f0(C("B7")) + f0(C("B61"))                            # 대출채권 관련 손실(대손상각비 등) + 기타대손상각비
        prov_gross = f0(C("B60"))                                         # 충당금전입액
        cost = C("B") - dae_gross - prov_gross
        dae = dae_gross - reversal
        provoth = prov_gross - a52                                        # 기타충당금적립
        sga, intc, secl = C("B5"), C("B4"), C("B2")
        fee_f = {"f_land": ("A122",), "f_mgmt": ("A123",), "f_disp": ("A124",), "f_coll": ("A125",), "f_pre": ("A126",),
                 "f_fund": ("A11",), "f_agent": ("A13",), "f_etc": ("A14",)}
        S = lambda c: self.g("SM025", c, "누계")
        fee_total = S("A1")
        IS_y = {"rev_raw": rev_raw, "rev": rev, "cost": cost, "ppop": rev - cost, "dae": dae, "dae_gross": dae_gross, "reversal": reversal,
                "provoth": provoth, "pretax": C("F"), "ni": C("G"), "nonop": f0(C("D")) - f0(C("E")),
                "reserve": C("G1"), "adjni": C("G2"),
                "r_fee": C("A1"), "r_sec": C("A2"), "r_int": C("A4"), "c_int": intc, "c_sga": sga, "c_sec": secl,
                "r_tlint": self.g("SM028", "A18", "누계")}
        IS_y["op"] = IS_y["ppop"] - dae - provoth
        IS_y["r_oth"] = rev - f0(IS_y["r_fee"]) - f0(IS_y["r_sec"]) - f0(IS_y["r_int"])
        IS_y["c_oth"] = cost - f0(intc) - f0(sga) - f0(secl)
        # 수수료수익 구성 (신탁유형별)
        for k, codes in fee_f.items():
            IS_y[k] = S(codes[0])
        IS_y["f_other_trust"] = S("A121") + f0(S("A127"))                  # 금전신탁 + 기타 신탁
        IS_y["f_trust"] = S("A12")                                        # 신탁보수 합계
        IS_y["f_total"] = fee_total
        # 한기평 영업수익 구성: 토지신탁수익 / 비토지신탁수익 / 부수업무수익(집합투자·대리업무·기타 수수료) / 이자수익
        IS_y["m_land"] = IS_y["f_land"]
        IS_y["m_nonland"] = f0(IS_y["f_mgmt"]) + f0(IS_y["f_disp"]) + f0(IS_y["f_coll"]) + f0(IS_y["f_pre"]) + f0(IS_y["f_other_trust"])
        IS_y["m_aux"] = f0(IS_y["f_fund"]) + f0(IS_y["f_agent"]) + f0(IS_y["f_etc"])
        IS_y["m_int"] = C("A4")
        IS_y["m_oth"] = rev - f0(IS_y["m_land"]) - f0(IS_y["m_nonland"]) - f0(IS_y["m_aux"]) - f0(IS_y["m_int"])
        IS_q = {k: self._flow(v) for k, v in IS_y.items()}
        self.IS_y, self.IS_q = IS_y, IS_q
        for k in IS_y:
            add_sum(f"is_{k}", IS_q[k])
            add_sum(f"is_{k}_ltm", self._ltm(IS_q[k]))
            add_sum(f"is_{k}_ytd", IS_y[k])
        add_share("ms_rev", rev_raw)
        add_share("ms_fee", fee_total)
        add_share("ms_land", IS_y["f_land"])

        # ================= 수익성 (한기평 정의: 누계 연환산 / (직전 결산말+당기말) 평균 자산)
        months = self._months()
        ann = 12.0 / months
        avg_a = (asset + self._prev_fye(asset, months)) / 2
        avg_e = (eq + self._prev_fye(eq, months)) / 2
        add_ratio("pf_roa", IS_y["ni"] * ann, avg_a)
        add_ratio("pf_roe", IS_y["ni"] * ann, avg_e)
        add_ratio("pf_ppop", IS_y["ppop"] * ann, avg_a)
        add_ratio("pf_dae", IS_y["dae"] * ann, avg_a)
        add_ratio("pf_op", IS_y["op"] * ann, avg_a)
        add_ratio("pf_sga", sga, rev)                                     # 판관비/영업수익
        add_ratio("pf_sgaa", sga * ann, avg_a)                            # 판관비용률 = 판관비 / 총자산평잔
        add_ratio("pf_nim", IS_y["ni"], rev)                              # 영업순이익률 = 당기순이익 / 영업수익
        add_ratio("pf_landsh", f0(IS_y["f_land"]) + f0(IS_y["r_tlint"]), rev_raw)    # 토지신탁수익비중 = (토지신탁 수수료 + 신탁계정대이자) / 영업수익
        add_ratio("pf_intsh", IS_y["r_int"], rev_raw)
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

        # ================= 자산건전성 (SM016 분류, 단위: 원)
        V = lambda it: g("SM016", "V", it)
        total, watch, fix, doubt, loss = V("합계"), V("요주의"), V("고정"), V("회수의문"), V("추정손실")
        sub = f0(fix) + f0(doubt) + f0(loss)
        sub = sub.where(total.notna())
        watch_up = sub + f0(watch)
        add_sum("aq_total", total); add_sum("aq_normal", V("정상")); add_sum("aq_watch", watch); add_sum("aq_fix", fix)
        add_sum("aq_doubt", doubt); add_sum("aq_loss", loss); add_sum("aq_sub", sub); add_sum("aq_watchup", watch_up)
        add_ratio("aq_subr", sub, total)                                  # 고정이하자산비중
        add_ratio("aq_watchr", watch_up, total)                           # 요주의이하자산비중
        add_ratio("aq_cov", allow_tot + eq, watch_up)                     # (충당금+자기자본)/요주의이하자산
        add_ratio("aq_netsub", sub - allow_tot, eq)                       # 자기자본 대비 순고정이하자산비율
        add_ratio("aq_tl_eq", tl - tl_allow, eq)
        add_ratio("aq_tl_ar", tl_allow, tl)
        K = lambda it: g("SM016", "K", it)
        tl_sub = f0(K("고정")) + f0(K("회수의문")) + f0(K("추정손실"))
        tl_tot = K("합계")
        add_sum("aq_tl_total", tl_tot); add_sum("aq_tl_sub", tl_sub.where(tl_tot.notna()))
        add_ratio("aq_tl_subr", tl_sub.where(tl_tot.notna()), tl_tot)    # 신탁계정대 고정이하 비중

        # ================= 자본적정성 (SM009 영업용순자본비율, SM011·SM012)
        nc, risk = g("SM009", "A"), g("SM009", "B")
        add_sum("cp_nc", nc); add_sum("cp_risk", risk); add_sum("cp_surplus", nc - risk)
        add_ratio("cp_ncr", nc, risk)
        add_ratio("cp_fixed", g("SM011", "A"), g("SM011", "B") + g("SM011", "C"))                   # 고정장기적합비율
        add_ratio("cp_lossw", g("SM012", "A"), g("SM012", "B") + g("SM012", "C"))                   # 손실위험도가중자산비율
        M["cp_dr"], M["cp_borrowr"], M["cp_netborrowr"], M["cp_lev"] = M["bs_dr"], M["bs_borrowr"], M["bs_netborrowr"], M["bs_lev"]

        # ================= 유동성 (SM010)
        add_sum("lq_assets", g("SM010", "A")); add_sum("lq_liab", g("SM010", "B"))
        add_ratio("lq_ratio", g("SM010", "A"), g("SM010", "B"))

    # ---- 회사 / 합산 시계열
    def payload(self) -> dict:
        names = self.names
        series: dict[str, dict] = {c: {} for c in names + [ALL_LABEL]}

        def to_list(row):
            return [None if (v is None or not np.isfinite(v)) else round(float(v), 3) for v in row]

        for key, m in self.metrics.items():
            if m["kind"] in ("sum", "share"):
                per = m["df"].reindex(names)
                agg = per.sum(min_count=1) if m["kind"] == "sum" else None
            else:
                num, den = m["num"].reindex(names), m["den"].reindex(names)
                ok = num.notna() & den.notna() & (den != 0)
                per = (num / den.where(den != 0)) * m["mult"]
                agg = num.where(ok).sum(min_count=1) / den.where(ok).sum(min_count=1) * m["mult"]
            for c in names:
                vals = to_list(per.loc[c].to_numpy())
                if any(v is not None for v in vals):
                    series[c][key] = vals
            if agg is not None:
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
    """FISIS 부동산신탁사 총자산·자기자본·ROA·영업용순자본비율·고정이하자산비중 (전체 리스트 탭용)."""
    td = TrustData()
    last = td.cal[-1]

    def val(key):
        m = td.metrics[key]
        if m["kind"] in ("sum", "share"):
            return m["df"][last]
        return m["num"][last] / m["den"][last].where(m["den"][last] != 0) * m["mult"]

    cols = {k: val(k) for k in ("bs_asset", "bs_equity", "pf_roa", "cp_ncr", "aq_subr")}
    pick = lambda x: None if x is None or not np.isfinite(x) else float(x)
    rows = [{"name": n, "asset": pick(cols["bs_asset"].get(n)), "equity": pick(cols["bs_equity"].get(n)), "roa": pick(cols["pf_roa"].get(n)),
             "ncr": pick(cols["cp_ncr"].get(n)), "sub": pick(cols["aq_subr"].get(n))}
            for n in td.names if pick(cols["bs_asset"].get(n))]
    return rows, format_ym(int(last))


def build_trust_payload() -> dict | None:
    if latest_final_df_path(SECTOR) is None:
        return None
    return TrustData().payload()


if __name__ == "__main__":
    p = build_trust_payload()
    print(len(p["quarters"]), p["quarters"][0], p["quarters"][-1], len(p["series"]), p["companies"])
