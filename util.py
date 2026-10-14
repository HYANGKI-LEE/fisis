import os

def make_dir(dir):
    os.makedirs(dir, exist_ok=True)  # 병렬 request.py 프로세스끼리 동시에 만들어도 안전

def long_df_file_name(lrgDivNm, smlDivNm, list_nm):
    return '{}_{}({}).csv'.format(lrgDivNm, smlDivNm, list_nm)