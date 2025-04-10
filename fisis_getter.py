import requests
import time
import warnings
import pandas as pd
from urllib3.exceptions import InsecureRequestWarning

import config

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

warnings.filterwarnings("ignore", category=InsecureRequestWarning, module="urllib3")
myAPIkey=config.myAPIkey
user_agent=config.user_agent


def getStatisticsListSearch(lrgDiv, smlDiv):
    response_method = 'json'
    url = f'http://fisis.fss.or.kr/openapi/statisticsListSearch.{response_method}?lang=kr&auth={myAPIkey}&lrgDiv={lrgDiv}&smlDiv={smlDiv}'
    headers = {'User-Agent': user_agent}
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        return None

def getAccountListSearch(listNo):
    response_method='json'
    url=f'http://fisis.fss.or.kr/openapi/accountListSearch.{response_method}?lang=kr&auth={myAPIkey}&listNo={listNo}'
    headers = {'User-Agent': user_agent}
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        return None

def getCompanySearch(partDiv):
    response_method='json'
    url=f'http://fisis.fss.or.kr/openapi/companySearch.{response_method}?lang=kr&auth={myAPIkey}&partDiv={partDiv}'
    headers = {'User-Agent': user_agent}
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        return None

def getStatisticsInfoSearch(financeCd, listNo, term, endBaseMm, startBaseMm='201001'):
    response_method='json'
    url=f'http://fisis.fss.or.kr/openapi/statisticsInfoSearch.{response_method}?lang=kr&auth={myAPIkey}&financeCd={financeCd}&listNo={listNo}&term={term}&startBaseMm={startBaseMm}&endBaseMm={endBaseMm}'
    headers = {'User-Agent': user_agent}
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}")
        return None


def getRawData_bySmlDiv(lrgDiv, smlDivNm, startBaseMm, endBaseMm, selected_items_file_name):
    selected_items = pd.read_excel(selected_items_file_name, index_col=0)
    target_items = selected_items[(selected_items['금융권역코드'] == lrgDiv) & (selected_items['통계표분류'] == smlDivNm) & (
                selected_items['사용여부'] == 1)].reset_index(drop=True)
    print(target_items)
    all_corp_list = [x for x in getCompanySearch(partDiv=lrgDiv)['result']['list'] if '[폐]' not in x['finance_nm']]
    print('')
    print(pd.DataFrame(all_corp_list))
    # pd.DataFrame(all_corp_list).to_csv('./저축은행 리스트.csv')
    # all_corp_list=[all_corp_list[0]]
    print('Total {} companies'.format(len(all_corp_list)))

    df = pd.DataFrame()
    for i, _finance_info in enumerate(all_corp_list):
        _finance_cd = _finance_info['finance_cd']
        _finance_dist = _finance_info['finance_path'].split('\\')[-2]
        _finance_nm = _finance_info['finance_nm']
        print('>>> {}: {}'.format(i + 1, _finance_nm))
        for i, r in target_items.iterrows():
            time.sleep(3)
            lrg_div_nm = r['금융권역명칭']
            sml_div_nm = r['통계표분류']
            list_no = r['통계코드']
            list_nm = r['통계명칭']
            result = getStatisticsInfoSearch(financeCd=_finance_cd,
                                             listNo=list_no,
                                             term='Q',  # 분기별 데이터
                                             startBaseMm=startBaseMm,
                                             endBaseMm=endBaseMm)['result']
            if result['err_cd'] == '000':  # if no errors
                df_tmp = pd.DataFrame(result['list'])
                df_tmp['finance_dist'] = _finance_cd
                df_tmp['finance_dist'] = _finance_dist
                df_tmp['sml_div_nm'] = sml_div_nm
                df_tmp['list_no'] = list_no
                df_tmp['list_nm'] = list_nm
                col_name_dict = {}
                for x in result['description']:
                    col_name_dict.update({x['column_id'].lower(): x['column_nm']})
                df = pd.concat([df, df_tmp.rename(columns=col_name_dict)])
    return df


def getRawData_byListNo(lrgDiv, smlDiv, startBaseMm, endBaseMm, term, listNo, listNm): #, selected_items_file_name):
    # selected_items = pd.read_excel(selected_items_file_name, index_col=0)
    # target_items = selected_items[(selected_items['금융권역코드'] == lrgDiv) & (selected_items['통계코드'] == listNo) & (
    #             selected_items['사용여부'] == 1)].reset_index(drop=True)
    all_corp_list = [x for x in getCompanySearch(partDiv=lrgDiv)['result']['list'] if '[폐]' not in x['finance_nm']]

    # if lrgDiv=='E':
    #   all_corp_list = [x for x in getCompanySearch(partDiv=lrgDiv)['result']['list']]

        # all_corp_list = all_corp_list[:5]
    # print('')
    # print(pd.DataFrame(all_corp_list))
    print('Total {} companies'.format(len(all_corp_list)))

    df = pd.DataFrame()
    for i, _finance_info in enumerate(all_corp_list):
        _finance_cd = _finance_info['finance_cd']
        _finance_dist = _finance_info['finance_path'].split('\\')[-2]
        _finance_nm = _finance_info['finance_nm']
        # print('>>> {}: {}'.format(i + 1, _finance_nm))

        # for i, r in target_items.iterrows():
        time.sleep(3)
        lrg_div_nm = lrgDiv # r['금융권역명칭']
        sml_div_nm = smlDiv # r['통계표분류']
        list_no = listNo # r['통계코드']
        list_nm = listNm # r['통계명칭']
        result = getStatisticsInfoSearch(financeCd=_finance_cd,
                                         listNo=list_no,
                                         term=term,  # 분기별 데이터
                                         startBaseMm=startBaseMm,
                                         endBaseMm=endBaseMm)['result']
        if result['err_cd'] == '000':  # if no errors
            df_tmp = pd.DataFrame(result['list'])
            df_tmp['finance_dist'] = _finance_cd
            df_tmp['finance_dist'] = _finance_dist
            df_tmp['sml_div_nm'] = sml_div_nm
            df_tmp['list_no'] = list_no
            df_tmp['list_nm'] = list_nm
            col_name_dict = {}
            for x in result['description']:
                col_name_dict.update({x['column_id'].lower(): x['column_nm']})
            df = pd.concat([df, df_tmp.rename(columns=col_name_dict)])
        else:
            print(result)
    return df