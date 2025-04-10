import os
import pandas as pd
from argparse import Namespace, ArgumentParser

from util import make_dir
from config import base_cols, col_name_matching_dict, Div_dict, smlDiv_dict, display_cols, Div_dict


def setup_args() -> Namespace:
    parser = ArgumentParser(description='fisis api')
    parser.add_argument('--lrgDiv_', type=str)
    return parser.parse_args()


if __name__ == '__main__':
    args = setup_args()
    lrgDivNm_ = Div_dict[args.lrgDiv_]["Name"]

    dir_lrgDiv='output/({}){}'.format(args.lrgDiv_, lrgDivNm_)
    make_dir(dir_lrgDiv)

    sml_divs = [f[1] for f in os.listdir(dir_lrgDiv) if not f.startswith('.') and f.startswith('(')]

    for sml_div in sml_divs:
        smlDivNm_=smlDiv_dict[sml_div]

        dir_smlDiv='{}/({}){}'.format(dir_lrgDiv, sml_div, smlDivNm_)
        make_dir(dir_smlDiv)

        dir_long_df='{}/long_df'.format(dir_smlDiv)
        make_dir(dir_long_df)

        dir_wide_df = '{}/wide_df'.format(dir_smlDiv)
        make_dir(dir_wide_df)

        periods = [f for f in os.listdir(dir_long_df) if not f.startswith('.')]
        max_start, max_end = max(periods).split('_')

        print("max_start", max_start, "max_end", max_end)
        print('')
        print(">> before deletion")
        print(periods)
        for period in periods:
            if period.startswith(max_start) and not period.endswith(max_end):
                periods.remove(period)
        print('')
        print(">> after deletion")
        print(periods)
        items = [f for f in os.listdir('{}/{}'.format(dir_long_df, periods[0])) if not f.startswith('.')]
        print('')
        print(items)

        n_rows=0
        for i in items:
            print('>>>> {} '.format(i))
            try:
                df=pd.DataFrame()
                for p in periods:
                    file_dir = '{}/{}/{}'.format(dir_long_df, p, i)
                    df_tmp = pd.read_csv(file_dir, index_col=[0], encoding='cp949')
                    df = pd.concat([df, df_tmp]).reset_index(drop=True)
                df['년월'] = df['년월'].astype('int')
                df['금융회사코드'] = df['금융회사코드'].astype('int')

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
                        except Exception as e:
                            print(e)

                if '항목' in df.columns:
                    display_cols_pivot=display_cols+['항목']
                else:
                    display_cols_pivot=display_cols

                wide_df = df.drop_duplicates().reset_index(drop=True).pivot(index=display_cols_pivot, columns='년월', values=value)

                n_rows_tmp=wide_df.shape[0]
                n_rows=n_rows+n_rows_tmp
                print('-- {} rows'.format(n_rows))
                print('')

                wide_df.reset_index().to_csv('{}/{}'.format(dir_wide_df, i), encoding='cp949')
            except Exception as e:
                print('-- passed! : {}'.format(e))
                print('')
                continue

        print('')
        print('>>>>>>> Total row counts : {} rows'.format(n_rows))