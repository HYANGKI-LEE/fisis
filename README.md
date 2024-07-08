# FISIS API


# Large Div의 전체 항목 추출하기

## step1. request API
- lrgDiv_ : 금융권역코드 (A : 국내은행, E : 상호저축은행)
- smlDiv_ : 통계표분류코드(B : 재무현황, C : 주요경영지표, D : 주요영업활동)
- startBaseMm_ : 검색시작년월
- endBaseMm_ : 검색종료년월

결과는 /output/.../long_df/ {startBaseMm_}_ {endBaseMm_} 에 저장
```commandline
python3 request.py --lrgDiv_ E --smlDiv_ B C --startBaseMm_ 201703 --endBaseMm_ 202312
```

## step2. process data : long to wide
- lrgDiv_ : 금융권역코드 (A : 국내은행, E : 상호저축은행)
- smlDiv_ : 통계표분류코드 (B : 재무현황, C : 주요경영지표, D : 주요영업활동)

[년월] 컬럼을 기준으로 pivot하여 long to wide 변환
1) (start, end) = ('200703', '201612')
2) (start, end) = ('201703', '202312')

결과는 /output/.../wide_df 에 저장
```commandline
python3 process.py --lrgDiv_ E
```

## step3. merge data
- smlDiv 내의 list 별로 나누어져 있는 파일을 하나로 merge (row append)

결과는 /output/.../final_df 에 저장 ({lrgDivNm} _ {smlDivNm} _ {endBaseMm}.csv)
```commandline
python3 merge.py --lrgDiv_ E
```

# List no로 추출하기

