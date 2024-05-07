
myAPIkey='c54ca82a0b77e3123cbb10e44a214812'
user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

base_cols=['base_month', 'finance_cd', 'finance_nm', 'account_cd', 'account_nm',
           'finance_dist', 'sml_div_nm', 'list_no', 'list_nm']

display_cols=['금융구분', '금융회사코드', '금융회사명', '통계분류', '통계표코드', '통계표명', '코드', '구분']

lrgDiv_dict={
    'A':'국내은행',
    'J':'외은지점',
    'H':'생명보험',
    'I':'손해보험',
    'F':'증권사',
    'W':'선물사',
    'G':'자산운용사',
    'D':'종합금융회사',
    'C':'신용카드사',
    'K':'리스사',
    'T':'할부금융사',
    'N':'신기술금융사',
    'E':'상호저축은행',
    'O':'신용협동조합',
    'Q':'농업협동조합',
    'P':'수산업협동조합',
    'S':'산림조합',
    'M':'부동산신탁',
    'L':'금융지주회사',
    'B':'공통(신탁)',
    'R':'공통(파생상품)'
}

smlDiv_dict={
    'A': '일반현황',
    'B': '재무현황',
    'C': '주요경영지표',
    'D': '주요영업활동',
    'E': '주요경영지표',
}

col_name_matching_dict={'base_month':'년월', 'finance_dist':'금융구분', 'finance_cd':'금융회사코드', 'finance_nm':'금융회사명',
                        'sml_div_nm':'통계분류', 'list_no':'통계표코드', 'list_nm':'통계표명', 'account_nm':'구분', 'account_cd':'코드'}
