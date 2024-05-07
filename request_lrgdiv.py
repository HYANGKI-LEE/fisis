import os
import time
import pandas as pd
from argparse import Namespace, ArgumentParser

import fisis_getter
from config import base_cols, col_name_matching_dict, lrgDiv_dict, smlDiv_dict, display_cols
from util import make_dir


# A 국내은행 / H 생명보험 / I 손해보험 / F 증권사 / K 리스사 / M 부동산신탁
# # (start, end) = ('200703', '201612')
# # (start, end) = ('201703', '202403')

def setup_args() -> Namespace:
    parser = ArgumentParser(description='fisis api')
    parser.add_argument('--lrgDiv_', type=str)
    parser.add_argument('--smlDiv_', type=str)
    parser.add_argument('--startBaseMm_', type=str)
    parser.add_argument('--endBaseMm_', type=str)
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

    dir_period='{}/{}_{}'.format(dir_long_df, args.startBaseMm_, args.endBaseMm_)
    make_dir(dir_period)

    list_list=fisis_getter.getStatisticsListSearch(lrgDiv=args.lrgDiv_, smlDiv=args.smlDiv_)['result']['list']
    # if True:
    #     list_list=[x for x in list_list if '08.03' in x['list_nm']]
    # # for x in list_list:
    # #     print(x['list_nm']
    print(list_list)
    print('')
    print('>>>>> Total {} lists <<<<<'.format(len(list_list)))
    print('')
    print('')
    for i, l in enumerate(list_list):
        list_no_=l['list_no']
        list_nm_=l['list_nm']
        print('')
        print('')
        print('>>>>> Stat List : {} ({} / {}) <<<<<'.format(list_nm_ , i+1, len(list_list)))
        start = time.time()
        term='Q'
        if list_no_ in ['SE010']: # 수익성
            term='Y'

        long_df = fisis_getter.getRawData_byListNo(lrgDiv=args.lrgDiv_,
                                                   smlDiv=args.smlDiv_,
                                                   startBaseMm=args.startBaseMm_,
                                                   endBaseMm=args.endBaseMm_,
                                                   term=term,
                                                   listNo=list_no_,
                                                   listNm=list_nm_)

        long_df.rename(columns=col_name_matching_dict, inplace=True)
        long_df.drop_duplicates().reset_index(drop=True).to_csv('{}/{}_{}({}).csv'.format(dir_period,
                                                 lrgDivNm_,
                                                 smlDivNm_,
                                                 list_nm_))  # , encoding='cp949')

        end = time.time()
        print("----> Done ! (Took {} minuites) - Columns : {}".format(round((end - start)/60),
                                                                      set(long_df.columns)-set(display_cols+["년월"])))
        del long_df
        time.sleep(30)