import config
import fisis_getter


all_corp_list = [x for x in fisis_getter.getCompanySearch(partDiv='E')['result']['list']]
filtered_corp_list = [x for x in fisis_getter.getCompanySearch(partDiv='E')['result']['list'] if '[폐]' not in x['finance_nm']]

print('>>>>> All - {} companies'.format(len(all_corp_list)))
print(all_corp_list)
print('')
print('')
print('>>>>> Filtered - {} companies'.format(len(filtered_corp_list)))
print(filtered_corp_list)



# print(fisis_getter.getStatisticsListSearch(lrgDiv='E',
#                                      smlDiv='C'))