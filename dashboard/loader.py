import glob
import os
import re

import pandas as pd

# 업권 표시명 -> output 폴더명
SECTOR_FOLDERS = {
    "국내은행": "(A)국내은행",
    "신용카드사": "(C)신용카드사",
    "상호저축은행": "(E)상호저축은행",
    "증권사": "(F)증권사",
    "자산운용사": "(G)자산운용사",
    "생명보험": "(H)생명보험",
    "손해보험": "(I)손해보험",
    "금융지주회사": "(L)금융지주회사",
    "리스사": "(K)리스사",
    "부동산신탁": "(M)부동산신탁",
    "신기술금융사": "(N)신기술금융사",
    "할부금융사": "(T)할부금융사",
}

# 여러 업권을 cross_append.py로 합쳐서 output/{이름}/{이름}_{최신분기}.csv로 만든 합산 업권 (캐피탈사 = 리스사 + 신기술금융사 + 할부금융사)
COMBINED_SECTORS = {"캐피탈사": "캐피탈사"}

# 대시보드 사이드바 순서 (데이터가 아직 없는 업권도 자리만 둔다)
DISPLAY_ORDER = [
    "국내은행", "신용카드사", "캐피탈사", "생명보험", "손해보험", "증권사", "자산운용사",
    "상호저축은행", "부동산신탁", "금융지주회사", "종합금융회사", "업권종합",
]

DATE_COL_RE = re.compile(r"^\d{6}$")


def _output_dir():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "output")


def latest_final_df_path(sector: str) -> str | None:
    if sector in COMBINED_SECTORS:
        folder = os.path.join(_output_dir(), COMBINED_SECTORS[sector])
        files = [f for f in glob.glob(os.path.join(folder, "*.csv*")) if "업데이트" not in f and f.endswith((".csv", ".csv.gz"))]
    elif sector in SECTOR_FOLDERS:
        final_dir = os.path.join(_output_dir(), SECTOR_FOLDERS[sector], "final_df")
        # 100MB를 넘는 final_df(예: 자산운용사)는 .csv.gz로 저장한다 - pandas가 확장자로 압축을 알아서 풀어 읽음
        files = [f for f in glob.glob(os.path.join(final_dir, "*.csv*")) if "업데이트" not in f and f.endswith((".csv", ".csv.gz"))]
    else:
        return None    # 데이터를 아직 수집하지 않은 업권
    if not files:
        return None

    def period_key(f):
        m = re.search(r"_(\d{6})\.csv(\.gz)?$", f)
        return m.group(1) if m else "000000"

    return max(files, key=period_key)


def load_sector_long(sector: str) -> pd.DataFrame:
    """업권 하나의 최신 final_df를 읽어 long format으로 변환.

    반환 컬럼: 금융회사명, 통계표명, 구분, 항목, 년월, 값
    """
    path = latest_final_df_path(sector)
    if path is None:
        return pd.DataFrame(columns=["금융회사명", "통계표명", "구분", "항목", "년월", "값"])

    df = pd.read_csv(path, encoding="cp949", low_memory=False)
    date_cols = [c for c in df.columns if DATE_COL_RE.match(c)]
    id_cols = [c for c in ["금융회사명", "통계표명", "구분", "항목"] if c in df.columns]

    long_df = df.melt(id_vars=id_cols, value_vars=date_cols, var_name="년월", value_name="값")
    long_df["값"] = pd.to_numeric(long_df["값"], errors="coerce")
    long_df = long_df.dropna(subset=["값"])
    long_df["년월"] = long_df["년월"].astype(int)
    return long_df
