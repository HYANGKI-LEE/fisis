"""증분으로 받은 새 분기 wide_df를, 로컬에 없는 과거 long_df를 다시 만들지 않고
기존 final_df(이미 git에 커밋돼 있는 전체 과거 이력)에 바로 합쳐넣는다.

merge.py를 그대로 못 쓰는 이유: merge.py는 wide_df 전체(= long_df 전체 기간)를
다시 모아서 final_df를 "새로 생성"하는 구조인데, 이 저장소는 final_df만 git에
남기고 long_df/wide_df는 로컬 전용(sparse-checkout)이라 과거 long_df가 없음.
그 상태로 merge.py를 돌리면 "이번에 받은 새 분기 데이터만" 있는 걸 가지고
final_df를 덮어써서 과거 이력이 통째로 날아감 (실제로 한 번 발생했던 사고).

대신 여기서는: 새로 생성된 wide_df(이번 신규 분기 컬럼 1개만 있음)를 분류별로
합친 뒤, 기존 final_df(과거 전체 컬럼 있음)와 공통 키 컬럼으로 outer merge해서
새 분기 컬럼만 추가한다.
"""
import glob
import os
import sys

import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from config import Div_dict, display_cols, smlDiv_dict  # noqa: E402
from dashboard.loader import latest_final_df_path  # noqa: E402

KEY_COLS = ["분류"] + display_cols + ["항목"]


def _read_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(path, index_col=[0], encoding="cp949", low_memory=False)


def build_new_quarter_df(lrgDiv: str, lrgDivNm: str) -> pd.DataFrame | None:
    """이번에 새로 돌린 process.py가 만든 wide_df들을, final_df와 같은 행 스키마
    (분류 + display_cols + 항목)로 맞춰서 smlDiv 전체를 합친 하나의 df로 반환."""
    sml_divs = Div_dict[lrgDiv]["SmlDiv"]
    combined = pd.DataFrame()

    for sml_div in sml_divs:
        sml_div_nm = smlDiv_dict[sml_div]
        wide_dir = os.path.join(
            REPO_ROOT, "output", f"({lrgDiv}){lrgDivNm}", f"({sml_div}){sml_div_nm}", "wide_df"
        )
        files = glob.glob(os.path.join(wide_dir, "*.csv"))
        if not files:
            continue

        part = pd.DataFrame()
        for f in files:
            df_tmp = _read_csv(f)
            part = pd.concat([part, df_tmp]).reset_index(drop=True)

        part["분류"] = sml_div_nm
        combined = pd.concat([combined, part]).reset_index(drop=True)

    if combined.empty:
        return None

    cols = [c for c in KEY_COLS if c in combined.columns]
    date_cols = [c for c in combined.columns if c not in KEY_COLS and c not in cols]
    return combined[cols + date_cols]


def merge_into_final_df(sector: str, lrgDiv: str, lrgDivNm: str) -> str | None:
    """새 분기 df를 기존 final_df와 합쳐서 새 final_df 파일을 쓰고 경로를 반환.
    새 데이터가 없으면 None."""
    new_df = build_new_quarter_df(lrgDiv, lrgDivNm)
    if new_df is None:
        return None

    old_path = latest_final_df_path(sector)
    if old_path is None:
        raise RuntimeError(f"{sector}: 기존 final_df가 없음 - 증분 병합 불가 (최초 적재 필요)")

    old_df = _read_csv(old_path)

    key_cols = [c for c in KEY_COLS if c in old_df.columns and c in new_df.columns]
    new_date_cols = [c for c in new_df.columns if c not in KEY_COLS]

    # 항목 컬럼이 NaN이면 merge key로 쓸 때 서로 매칭이 안 될 수 있어 임시 치환
    sentinel = "__NA__"
    old_keyed = old_df.copy()
    new_keyed = new_df.copy()
    for c in key_cols:
        old_keyed[c] = old_keyed[c].fillna(sentinel)
        new_keyed[c] = new_keyed[c].fillna(sentinel)

    merged = old_keyed.merge(new_keyed[key_cols + new_date_cols], on=key_cols, how="outer")
    for c in key_cols:
        merged[c] = merged[c].replace(sentinel, pd.NA)

    new_period = new_date_cols[0]
    new_path = os.path.join(os.path.dirname(old_path), f"{lrgDivNm}_{new_period}.csv")
    merged.to_csv(new_path, encoding="cp949")
    return new_path
