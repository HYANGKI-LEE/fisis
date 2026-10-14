import os
import time
import pandas as pd
from argparse import Namespace, ArgumentParser

import fisis_getter
from config import base_cols, col_name_matching_dict, smlDiv_dict, Div_dict, display_cols
from util import make_dir, long_df_file_name


# A 국내은행 / H 생명보험 / I 손해보험 / F 증권사 / K 리스사 / M 부동산신탁 / E 상호저축은행
# # (start, end) = ('200703', '201612')
# # (start, end) = ('201703', '202403')

def setup_args() -> Namespace:
    parser = ArgumentParser(description='fisis api')
    parser.add_argument('--lrgDiv_', type=str)
    parser.add_argument('--startBaseMm_', type=str)
    parser.add_argument('--endBaseMm_', type=str)
    parser.add_argument('--shard', type=str, default='0/1',
                        help='i/n - 통계표 목록을 n등분해 i번째만 수집 (최초 적재를 병렬로 돌릴 때 사용)')
    return parser.parse_args()

if __name__ == '__main__':
    args = setup_args()
    lrgDivNm_ = Div_dict[args.lrgDiv_]["Name"]
    smlDiv_ = Div_dict[args.lrgDiv_]["SmlDiv"]
    dir_lrgDiv='output/({}){}'.format(args.lrgDiv_, lrgDivNm_)
    make_dir(dir_lrgDiv)

    for sml_div in smlDiv_:
        smlDivNm_ = smlDiv_dict[sml_div]
        dir_smlDiv = '{}/({}){}'.format(dir_lrgDiv, sml_div, smlDivNm_)
        make_dir(dir_smlDiv)

        dir_long_df = '{}/long_df'.format(dir_smlDiv)
        make_dir(dir_long_df)

        dir_period = '{}/{}_{}'.format(dir_long_df, args.startBaseMm_, args.endBaseMm_)
        make_dir(dir_period)

        list_list = fisis_getter.getStatisticsListSearch(lrgDiv=args.lrgDiv_, smlDiv=sml_div)['result']['list']
        print(list_list)

        shard_i, shard_n = [int(x) for x in args.shard.split('/')]
        # 완료 여부 필터 전에 나눠야 재시도 때 분담이 안 바뀜
        list_list = [l for j, l in enumerate(list_list) if j % shard_n == shard_i]

        list_for_target=[]
        for list_ in list_list:
            file_name=long_df_file_name(list_['lrg_div_nm'], list_['sml_div_nm'], list_['list_nm'])
            check_completed = [x for x in os.listdir(dir_period) if x == file_name]
            if not check_completed:
                list_for_target.append(list_)

        # print(list_for_target)

        print('>>>>> Total {} lists <<<<<'.format(len(list_for_target)))
        print('')
        print('')

        for i, l in enumerate(list_for_target):
            list_no_=l['list_no']
            list_nm_=l['list_nm']
            print('')
            print('')
            print('>>>>> Stat List : {} ({} / {}) <<<<<'.format(list_nm_ , i+1, len(list_for_target)))
            full_file_name = '{}/{}'.format(dir_period, long_df_file_name(lrgDivNm_, smlDivNm_, list_nm_))
            print(full_file_name)
            if os.path.isfile(full_file_name):
                print("--This file is passed")
                continue
            else:
                start = time.time()
                term='Q'
                if list_no_ in ['SE010']: # 수익성
                    term='Y'

                long_df = fisis_getter.getRawData_byListNo(lrgDiv=args.lrgDiv_,
                                                           smlDiv=sml_div,
                                                           startBaseMm=args.startBaseMm_,
                                                           endBaseMm=args.endBaseMm_,
                                                           term=term,
                                                           listNo=list_no_,
                                                           listNm=list_nm_)

                long_df.rename(columns=col_name_matching_dict, inplace=True)
                long_df.drop_duplicates().reset_index(drop=True).to_csv(full_file_name, encoding='cp949')

                end = time.time()
                print("----> Done ! (Took {} minuites) - Columns : {}".format(round((end - start)/60),
                                                                              set(long_df.columns)-set(display_cols+["년월"])))
                del long_df
                time.sleep(30)