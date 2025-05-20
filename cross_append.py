import os
import pandas as pd
from argparse import Namespace, ArgumentParser

from util import make_dir
from config import base_cols, col_name_matching_dict, Div_dict, smlDiv_dict, display_cols


def setup_args() -> Namespace:
    parser = ArgumentParser(description='fisis api')
    parser.add_argument('--Category_', type=str)
    return parser.parse_args()

if __name__ == '__main__':
    args = setup_args()

    if args.Category_ == "보험사":
        dir_category = 'output/{}'.format(args.Category_)
        lrgDiv_list = ["H", "I"]

    elif args.Category_ == "캐피탈사":
        dir_category = 'output/{}'.format(args.Category_)
        lrgDiv_list = ["K", "N", "T"]

    make_dir(dir_category)

    df = pd.DataFrame()
    for ll in lrgDiv_list:
        lrgDivNm_ = Div_dict[ll]["Name"]

        dir_lrgDiv = 'output/({}){}'.format(ll, lrgDivNm_)
        make_dir(dir_lrgDiv)

        dir_final_df = '{}/final_df'.format(dir_lrgDiv)
        make_dir(dir_final_df)

        items = sorted([f for f in os.listdir(dir_final_df) if not f.startswith('.')])
        file_dir = '{}/{}'.format(dir_final_df, items[-1])

        df_tmp = pd.read_csv(file_dir, index_col=[0], encoding='cp949')
        df = pd.concat([df, df_tmp], ignore_index=True)

    data_cols = sorted(list(set(df.columns) - set(display_cols + ['항목'] + ['분류'])))
    print(display_cols)
    print('')
    print(data_cols)

    df.reset_index(drop=True).to_csv('{}/{}_{}.csv'.format(dir_category, args.Category_, data_cols[-1]),
                                           encoding='cp949')

