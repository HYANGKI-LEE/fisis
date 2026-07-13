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
    "생명보험": "(H)생명보험",
    "손해보험": "(I)손해보험",
    "리스사": "(K)리스사",
    "부동산신탁": "(M)부동산신탁",
    "신기술금융사": "(N)신기술금융사",
    "할부금융사": "(T)할부금융사",
}

DATE_COL_RE = re.compile(r"^\d{6}$")


def _output_dir():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "output")


def latest_final_df_path(sector: str) -> str | None:
    folder = SECTOR_FOLDERS[sector]
    final_dir = os.path.join(_output_dir(), folder, "final_df")
    files = [f for f in glob.glob(os.path.join(final_dir, "*.csv")) if "업데이트" not in f]
    if not files:
        return None

    def period_key(f):
        m = re.search(r"_(\d{6})\.csv$", f)
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
