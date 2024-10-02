import os

def make_dir(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)

def long_df_file_name(lrgDivNm, smlDivNm, list_nm):
    return '{}_{}({}).csv'.format(lrgDivNm, smlDivNm, list_nm)