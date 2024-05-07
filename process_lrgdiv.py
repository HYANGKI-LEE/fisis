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
    lrgDivNm_=lrgDiv_dict[args.lrgDiv_]
    smlDivNm_=smlDiv_dict[args.smlDiv_]

    dir_lrgDiv='output/({}){}'.format(args.lrgDiv_, lrgDivNm_)
    make_dir(dir_lrgDiv)

    dir_smlDiv='{}/({}){}'.format(dir_lrgDiv, args.smlDiv_, smlDivNm_)
    make_dir(dir_smlDiv)

    dir_long_df='{}/long_df'.format(dir_smlDiv)
    make_dir(dir_long_df)

    dir_wide_df = '{}/wide_df'.format(dir_smlDiv)
    make_dir(dir_wide_df)

    periods = [f for f in os.listdir(dir_long_df) if not f.startswith('.')]
    items = [f for f in os.listdir('{}/{}'.format(dir_long_df, periods[0])) if not f.startswith('.')]
    # print(items)
    n_rows=0
    for i in items:
        print('>>>> {} '.format(i))
        try:
            df=pd.DataFrame()
            for p in periods:
                file_dir = '{}/{}/{}'.format(dir_long_df, p, i)
                df_tmp = pd.read_csv(file_dir, index_col=[0])
                df = pd.concat([df, df_tmp]).reset_index(drop=True)
            df['년월'] = df['년월'].astype('int')
            df['금융회사코드'] = df['금융회사코드'].astype('int')
            # df=df.drop_duplicates().reset_index(drop=True)
            value_cols=list(set(df.columns)-set(display_cols+['년월']))
            print(value_cols)
            if len(value_cols) == 0:
                continue
            if len(value_cols) == 1:
                value=value_cols[0]
            else:
                if '금액' in value_cols:
                    value='금액'
                elif '당분기' in value_cols:
                    value='당분기'
                else:
                    try:
                        df=pd.melt(df, id_vars=display_cols+['년월'], value_vars=value_cols).rename(columns={"variable": "항목", "value": "금액"})
                        value='금액'
                        # print(df)
                    except Exception as e:
                        print(e)

                    # print('! New case - {}'.format(value_cols))
            # print(value)
            # print(df.head(5))
            # print('')
            #print(df.shape[0])
            # print(df.drop_duplicates().shape[0](5))
            #print(df.drop_duplicates().shape[0])
            # print(display_cols)
            # aa=df.drop_duplicates().groupby(display_cols + ['년월']).size().sort_values(ascending=False).reset_index(name='count')
            # print(aa)
            if '항목' in df.columns:
                display_cols_pivot=display_cols+['항목']
            else:
                display_cols_pivot=display_cols
            # print(df)
            wide_df = df.drop_duplicates().reset_index(drop=True).pivot(index=display_cols_pivot, columns='년월', values=value)
            # print(wide_df.head(5))
            n_rows_tmp=wide_df.shape[0]
            n_rows=n_rows+n_rows_tmp
            print('-- {} rows'.format(n_rows))
            print('')
            # print(dir_wide_df)
            # print(i)
            wide_df.reset_index().to_csv('{}/{}'.format(dir_wide_df, i), encoding='cp949')
        except Exception as e:
            print('-- passed! : {}'.format(e))
            print('')
            continue

    print('')
    print('>>>>>>> Total row counts : {} rows'.format(n_rows))