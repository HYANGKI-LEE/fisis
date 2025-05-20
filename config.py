
myAPIkey='c54ca82a0b77e3123cbb10e44a214812'
user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

base_cols=['base_month', 'finance_cd', 'finance_nm', 'account_cd', 'account_nm',
           'finance_dist', 'sml_div_nm', 'list_no', 'list_nm']

display_cols=['금융구분', '금융회사코드', '금융회사명', '통계분류', '통계표코드', '통계표명', '코드', '구분']

Div_dict={
    'A': {'Name' : '국내은행',
          'SmlDiv' : ["B", "C", "D"]},
    'J': {'Name' : '외은지점',
          'SmlDiv' : ["B", "C"]},
    'H': {'Name' : '생명보험',
          'SmlDiv' : ["B", "C", "D"]},
    'I': {'Name' : '손해보험',
          'SmlDiv' : ["B", "C", "D"]},
    'F': {'Name' : '증권사',
          'SmlDiv' : ["B", "C", "D"]},
    'W': {'Name' : '선물사',
          'SmlDiv' : ["B", "C", "D"]},
    'G': {'Name' : '자산운용사',
          'SmlDiv' : ["B", "C", "D"]},
    'D': {'Name' : '종합금융회사',
          'SmlDiv' : ["B", "C"]},
    'C': {'Name' : '신용카드사',
          'SmlDiv' : ["B", "C", "D"]},
    'K': {'Name' : '리스사',
          'SmlDiv' : ["B", "C"]},
    'T': {'Name' : '할부금융사',
          'SmlDiv' : ["B", "C"]},
    'N': {'Name' : '신기술금융사',
          'SmlDiv' : ["B", "C"]},
    'E': {'Name' : '상호저축은행',
          'SmlDiv' : ["B", "C"]},
    'O': {'Name' : '신용협동조합',
          'SmlDiv' : ["B", "C"]},
    'Q': {'Name' : '농업협동조합',
          'SmlDiv' : ["B", "C"]},
    'P': {'Name' : '수산업협동조합',
          'SmlDiv' : ["B", "C"]},
    'S': {'Name' : '산림조합',
          'SmlDiv' : ["B", "C"]},
    'M': {'Name' : '부동산신탁',
          'SmlDiv' : ["B", "E"]},
    'L': {'Name' : '금융지주회사',
          'SmlDiv' : ["B", "C"]},
    'B': {'Name' : '공통(신탁)',
          'SmlDiv' : ["A", "B", "C", "D", "E", "F"]},
    'R': {'Name' : '공통(파생상품)',
          'SmlDiv' : ["A", "B"]}
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
