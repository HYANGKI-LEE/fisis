import os
import pandas as pd
from argparse import Namespace, ArgumentParser

from util import make_dir
from config import base_cols, col_name_matching_dict, lrgDiv_dict, smlDiv_dict, display_cols


def setup_args() -> Namespace:
    parser = ArgumentParser(description='fisis api')
    parser.add_argument('--lrgDiv_', type=str)
    parser.add_argument('--smlDiv_', type=str)
    return parser.parse_args()


if __name__ == '__main__':
    args = setup_args()
    lrgDivNm_ = lrgDiv_dict[args.lrgDiv_]
    smlDivNm_ = smlDiv_dict[args.smlDiv_]

    dir_lrgDiv = 'output/({}){}'.format(args.lrgDiv_, lrgDivNm_)
    make_dir(dir_lrgDiv)

    dir_smlDiv = '{}/({}){}'.format(dir_lrgDiv, args.smlDiv_, smlDivNm_)
    make_dir(dir_smlDiv)

    dir_long_df = '{}/long_df'.format(dir_smlDiv)
    make_dir(dir_long_df)

    dir_wide_df = '{}/wide_df'.format(dir_smlDiv)
    make_dir(dir_wide_df)

    dir_final_df = '{}/final_df'.format(dir_smlDiv)
    make_dir(dir_final_df)

    items = [f for f in os.listdir(dir_wide_df) if not f.startswith('.')]

    df = pd.DataFrame()
    for i in items:
        file_dir = '{}/{}'.format(dir_wide_df, i)
        df_tmp = pd.read_csv(file_dir, index_col=[0], encoding='cp949')
        # print(">>> {}".format(file_dir))
        # print(df_tmp.columns)
        df = pd.concat([df, df_tmp]).reset_index(drop=True)
    data_cols=sorted(list(set(df.columns)-set(display_cols+['항목'])))
    # print(data_cols)
    if '항목' in df.columns:
        display_cols_sort = display_cols + ['항목']
    else:
        display_cols_sort = display_cols
    df=df[display_cols_sort+data_cols]
    df.reset_index(drop=True).to_csv('{}/{}_{}_{}.csv'.format(dir_final_df, lrgDivNm_, smlDivNm_, data_cols[-1]), encoding='cp949')