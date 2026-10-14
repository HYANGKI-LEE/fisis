"""3사(한기평 KR / 한신평 KIS / NICE) 증권업 자료에서 대형·중소형 분류와 신용등급을 뽑아 data/securities_peers.json 으로 저장.

- KR  : (Data Sheet) 증권업 재무자료 - 종합IB 9개사 = 대형, 일반증권사 = 중소형 / 신용등급현황 시트(장기(전망)/단기)
- 한신평: 증권업DataPackage - Peer Snapshot 회사 순서와 대형/중소형 자산총계 합계로 구성원을 역산 / 신용등급 현황 시트
- NICE: 증권 NDB - 산업(횡단면)_대형IB / 중형사 / 소형사 시트의 회사 열 (중형사+소형사 = 중소형). 신용등급은 NDB에 없어서
      NICE Market Comment 부록 표(2026.06)를 NICE_RATINGS에 옮겨 적었다.
엑셀 원본은 저장소에 올리지 않고(.gitignore) 이 스크립트가 만든 JSON만 쓴다.

사용: python scripts/extract_securities_peers.py [KR엑셀] [한신평엑셀] [NICE엑셀]
"""
import json
import sys
import warnings
from pathlib import Path

import openpyxl

warnings.filterwarnings("ignore")
REPO_DIR = Path(__file__).resolve().parent.parent
OUT = REPO_DIR / "data" / "securities_peers.json"
DL = Path.home() / "Downloads"
KR_XLSX = DL / "(Data Sheet) 증권업 재무자료_2026.2Q.xlsx"
KIS_XLSX = DL / "증권업DataPackage-2026.2Q_IS20261012-1.xlsx"
NICE_XLSX = DL / "증권 NDB(NICE DATA BOOK)[2026.2Q].xlsx"

# 회사 이름(3사 표기) -> FISIS 금융회사코드
CODE_BY_NAME = {
    "미래에셋증권": 10094, "미래": 10094, "한국투자증권": 10129, "한투": 10129, "NH투자증권": 10101, "NH": 10101,
    "삼성증권": 10119, "삼성": 10119, "KB증권": 10106, "KB": 10106, "하나증권": 10130, "하나": 10130,
    "신한투자증권": 10091, "신한": 10091, "키움증권": 10136, "키움": 10136, "대신증권": 10093, "대신": 10093,
    "교보증권": 10090, "교보": 10090, "한화투자증권": 10110, "한화": 10110, "신영증권": 10095, "신영": 10095,
    "유안타증권": 10113, "유안타": 10113, "현대차증권": 10111, "현대차": 10111, "IBK투자증권": 12001, "IBK": 12001,
    "BNK투자증권": 12334, "BNK": 12334, "아이엠증권": 10128, "IM증권": 10128, "아이엠": 10128,
    "유진투자증권": 10097, "유진": 10097, "DB증권": 10120, "DB": 10120, "엘에스증권": 10137, "LS증권": 10137, "엘에스": 10137,
    "다올투자증권": 11981, "다올": 11981, "SK증권": 10114, "SK": 10114, "한양증권": 10098, "한양": 10098,
    "디에스투자증권": 11980, "DS투자증권": 11980, "케이프투자증권": 11978, "상상인증권": 10104, "상상인": 10104,
    "카카오페이증권": 11982, "카카오": 11982, "메리츠증권": 10099, "메리츠": 10099, "부국증권": 10102, "부국": 10102,
    "유화증권": 10112, "유화": 10112, "리딩투자증권": 10132, "리딩": 10132, "노무라": 12390, "노무라금융투자": 12390,
    "우리투자증권": 13515, "우리": 13515,
}


def code(name: str) -> int:
    n = str(name).strip()
    if n not in CODE_BY_NAME:
        raise KeyError(f"회사 이름을 FISIS 코드로 못 바꿈: {n}")
    return CODE_BY_NAME[n]


def kr(path: Path) -> dict:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["2026(06)"]
    names = []
    for c in range(6, ws.max_column + 1):
        v = ws.cell(4, c).value
        if v in (None, ""):
            break
        if isinstance(v, str) and v.strip() not in ("업권 합계",):
            names.append(v.strip())
        if v == "업권 합계":
            break
    names = [n for n in names if "합계" not in n and "평균" not in n]
    groups = {}
    for i, n in enumerate(names):
        groups[code(n)] = "대형" if i < 9 else "중소형"          # 종합IB 9개사(F:N) / 일반증권사
    # 신용등급현황: 헤더 4행에서 가장 최근 시점 열
    rs = wb["신용등급현황"]
    hdr = {rs.cell(4, c).value: c for c in range(6, rs.max_column + 1) if rs.cell(4, c).value}
    col = hdr["2026(06)"]
    ratings = {}
    for r in range(5, rs.max_row + 1):
        n = rs.cell(r, 5).value
        v = rs.cell(r, col).value
        if isinstance(n, str) and n.strip() in CODE_BY_NAME:
            ratings[code(n)] = None if v in (None, "", "-", "n.a.") else str(v).strip()
    return {"groups": groups, "ratings": ratings, "asof": "2026.06"}


def kis(path: Path) -> dict:
    wb = openpyxl.load_workbook(path, data_only=True)
    ps = wb["Peer Snapshot"]
    names, assets = [], []
    for c in range(6, ps.max_column + 1):
        n = ps.cell(6, c).value
        if not isinstance(n, str) or not n.strip():
            break
        names.append(n.strip())
        assets.append(float(ps.cell(9, c).value))
    # 대형 구성원 = Peer 순서 앞에서부터 자산총계 누적합이 대형 합계(Peer 비교 시트 2026.06)와 같아지는 지점까지
    pb = wb["Peer 비교"]
    hdr = {}
    for c in range(6, 14):
        hdr[c] = (pb.cell(7, c).value, pb.cell(8, c).value)
    big_total = None
    for r in range(9, 14):
        if str(pb.cell(r, 5).value).strip() == "자산총계":
            big_total = float(pb.cell(r, 9).value)      # 대형 2026.06
    acc, k = 0.0, 0
    for i, a in enumerate(assets):
        acc += a
        if abs(acc - big_total) < 1.0:
            k = i + 1
            break
    assert k, "한신평 대형 구성원을 역산하지 못함"
    groups = {code(n): ("대형" if i < k else "중소형") for i, n in enumerate(names)}
    rs = wb["신용등급 현황"]
    hdr = {str(rs.cell(6, c).value).strip(): c for c in range(6, rs.max_column + 1) if rs.cell(6, c).value}
    col = hdr.get("2026.06") or hdr.get("2026.6") or max(hdr.values())     # 가장 최근 열
    ratings = {}
    for r in range(8, rs.max_row + 1):
        n = rs.cell(r, 5).value
        v = rs.cell(r, col).value
        if isinstance(n, str) and n.strip() in CODE_BY_NAME:
            ratings[code(n)] = None if v in (None, "", "-") else str(v).strip()
    return {"groups": groups, "ratings": ratings, "asof": "2026.06", "big_members": names[:k]}


# NICE신용평가 Market Comment 부록 '증권업 신용등급 분포 및 추이'(2026.06 열) 표를 옮겨 적음: 이름 -> (장기, 단기), None = 표에서 '-'
NICE_RATINGS = {
    "한국투자증권": ("AA/S", "A1"), "미래에셋증권": ("AA/S", "A1"), "NH투자증권": ("AA+/S", "A1"), "삼성증권": ("AA+/S", None),
    "메리츠증권": ("AA/S", "A1"), "KB증권": ("AA+/S", "A1"), "하나증권": ("AA/S", None), "키움증권": ("AA/S", "A1"),
    "신한투자증권": ("AA/S", "A1"), "대신증권": ("AA-/S", "A1"), "우리투자증권": (None, "A1"), "교보증권": ("AA-/S", "A1"),
    "한화투자증권": ("AA-/S", "A1"), "유안타증권": ("AA-/S", "A1"), "신영증권": ("AA-/S", "A1"), "현대차증권": ("AA-/S", "A1"),
    "IBK투자증권": ("AA-/S", "A1"), "BNK투자증권": ("A+/S", "A1"), "IM증권": (None, "A1"), "유진투자증권": ("A/S", "A2+"),
    "DB증권": ("A+/S", "A1"), "LS증권": ("A/S", "A2+"), "부국증권": (None, "A2+"), "다올투자증권": ("BBB+/S[후]", "A2-"),
    "SK증권": ("BBB+/S[후]", "A2"), "한양증권": (None, "A2"), "DS투자증권": ("A-/S", "A2-"), "케이프투자증권": ("A-/S", "A2-"),
    "리딩투자증권": ("BBB+/P", "A3+"),
}


def _nice_rating(long_, short):
    if long_ and short:
        return f"{long_} · {short}"
    if long_:
        return long_
    return f"{short}(단기)" if short else None


def nice(path: Path) -> dict:
    wb = openpyxl.load_workbook(path, data_only=True)
    groups, detail = {}, {}
    for sheet, grp, label in (("산업(횡단면)_대형IB", "대형", "대형IB"), ("산업(횡단면)_중형사", "중소형", "중형사"),
                              ("산업(횡단면)_소형사", "중소형", "소형사")):
        ws = wb[sheet]
        for c in range(4, ws.max_column + 1):
            n = ws.cell(5, c).value
            if n in ("합산", "평균", "산업평균"):
                break
            if isinstance(n, str) and n.strip():
                groups[code(n)] = grp
                detail[code(n)] = label
    ratings = {code(n): _nice_rating(*v) for n, v in NICE_RATINGS.items()}
    return {"groups": groups, "detail": detail, "ratings": ratings, "asof": "2026.06"}


def main():
    a = sys.argv[1:]
    out = {
        "KR": kr(Path(a[0]) if len(a) > 0 else KR_XLSX),
        "KIS": kis(Path(a[1]) if len(a) > 1 else KIS_XLSX),
        "NICE": nice(Path(a[2]) if len(a) > 2 else NICE_XLSX),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in out.items():
        n_big = sum(1 for g in v["groups"].values() if g == "대형")
        print(f"{k}: 대형 {n_big} / 중소형 {len(v['groups']) - n_big} / 등급 {sum(1 for r in v['ratings'].values() if r)}개")


if __name__ == "__main__":
    main()
