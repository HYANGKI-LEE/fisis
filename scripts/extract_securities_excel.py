"""증권업 재무자료 엑셀(한국기업평가 Data Sheet)에서 FISIS API로는 못 구하는 항목만 뽑아 JSON으로 저장.

엑셀 자체는 저장소에 올리지 않고(.gitignore) 이 스크립트가 만든 data/securities_excel.json 만 사용한다.
FISIS로 구할 수 있는 항목(재무상태표/손익계산서/NCR/유동성 등)은 sec_charts.py가 FISIS에서 직접 계산하고,
엑셀 값은 검증용(verify_securities.py)으로만 쓴다.

사용: python scripts/extract_securities_excel.py "엑셀경로"
"""
import json
import re
import sys
import warnings
from pathlib import Path

import openpyxl

warnings.filterwarnings("ignore")

REPO_DIR = Path(__file__).resolve().parent.parent
OUT = REPO_DIR / "data" / "securities_excel.json"

PERIOD_RE = re.compile(r"^(\d{4})\((\d{2})\)$")
SKIP_COLS = {"업권 합계", "종합IB 합계", "일반증권사 합계", "업권 평균", "종합IB 평균", "일반증권사 평균"}

# 엑셀 행 라벨(같은 라벨이 여러 번 나오는 건 "라벨#n"으로 n번째 등장) -> 내부 키
# FISIS에서 못 구하는 항목만 데이터로 쓰고, 나머지는 검증용으로 같이 뽑아 둔다.
EXCEL_KEYS = {
    # 영업순수익 구성
    "위탁매매": "ex_brokerage", "상품운용": "ex_trading", "투자은행": "ex_ib", "자산관리": "ex_wm", 
    # 자본적정성
    "수정영업용순자본(연결)": "ex_adj_ncap", "수정총위험액(연결)": "ex_adj_risk", "수정NCR": "ex_adj_ncr",
    "조정레버리지배율(배)": "ex_adj_lev",
    # 유동성
    "조정유동성비율": "ex_adj_liq", "우발채무/유동성GAP": "ex_cont_gap",
    # 파생결합증권
    "ELS·ELB": "ex_els", "DLS·DLB": "ex_dls", "자헤체지 ELS·DLS": "ex_hedge", "자헤체지 ELS·DLS/자기자본": "ex_hedge_eq",
    "자체헤지 ELS·DLS/유동성GAP": "ex_hedge_gap",
    # 우발채무
    "우발채무": "ex_cont", "우발채무/자기자본": "ex_cont_eq",
}


def extract(xlsx: Path) -> dict:
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    periods = []
    data: dict[str, dict] = {}
    for name in wb.sheetnames:
        m = PERIOD_RE.match(name)
        if not m:
            continue
        ym = f"{m.group(1)}{m.group(2)}"
        ws = wb[name]
        seen: dict[str, int] = {}
        row_key: dict[int, str] = {}
        for r in range(5, 125):
            lab = ws.cell(r, 5).value
            if not isinstance(lab, str):
                continue
            lab = lab.strip()
            seen[lab] = seen.get(lab, 0) + 1
            key = EXCEL_KEYS.get(lab)
            if r == 83 and lab == "기타":     # 영업순수익 구성의 '기타' (같은 라벨이 여러 번 나오므로 행 번호로 지정)
                key = "ex_otherrev"
            if key:
                row_key[r] = key
        cols = {}
        for c in range(6, ws.max_column + 1):
            co = ws.cell(4, c).value
            if isinstance(co, str) and co.strip() and co.strip() not in SKIP_COLS:
                cols[c] = co.strip()
            elif co is None and cols:
                break
        per = {}
        for c, co in cols.items():
            vals = {}
            for r, key in row_key.items():
                v = ws.cell(r, c).value
                if isinstance(v, (int, float)):
                    vals[key] = float(v)
            if vals:
                per[co] = vals
        periods.append(ym)
        data[ym] = per
    periods.sort()
    return {"periods": periods, "data": data}


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\infomax\Downloads\(Data Sheet) 증권업 재무자료_2026.2Q.xlsx")
    out = extract(src)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    n = sum(len(v) for v in out["data"].values())
    print(f"저장: {OUT} (기간 {len(out['periods'])}개: {out['periods'][0]}~{out['periods'][-1]}, 회사x기간 {n}건)")


if __name__ == "__main__":
    main()
