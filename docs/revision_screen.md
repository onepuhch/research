# 이익 예상치 상향 스크리너

최신 시도: 2026-10-21 14:00 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-21 14:00 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7645|7645|0|0|0|
|EPS 예상치|3233|2418|815|0|0|
|업종(후보)|96|96|0|0|0|
|주가 비교(상위)|31|31|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 16곳: COP, OXY, FANG, PR, OVV, APA, AR, SM, CHRD, MTDR, MUR, CRGY, NOG, KOS, TXO, GRNT
- **Oil & Gas Integrated** 8곳: CVX, SHEL, TTE, BP, EQNR, E, EC, DEC
- **Oil & Gas Refining & Marketing** 8곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR
- **Semiconductors** 6곳: NVDA, MU, INTC, ALAB, LSCC, SMTC
- **Computer Hardware** 5곳: DELL, SNDK, STX, WDC, P
- **Software - Application** 5곳: TEAM, MNDY, FSLY, PUBM, CMRC
- **Semiconductor Equipment & Materials** 4곳: ACMR, AXTI, AEHR, ICHR
- **Steel** 3곳: NUE, STLD, CLF
- **Oil & Gas Midstream** 3곳: VG, FRO, DHT
- **Banks - Regional** 3곳: HBT, AMTB, BSVN

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$990M|$2.69 → $7.40|+175%|+32.87%p|2/0|+8%|-61%|예|
|2|PBF|Oil & Gas Refining & Marketing|$9.8B|$7.74 → $18.51|+139%|+12.97%p|3/1|+34%|-44%|예|
|3|DK|Oil & Gas Refining & Marketing|$4.8B|$3.05 → $9.03|+196%|+7.70%p|4/0|+20%|-60%|예|
|4|TXO|Oil & Gas E&P|$779M|$0.88 → $1.92|+119%|+7.44%p|1/0|+6%|-52%|예|
|5|PARR|Oil & Gas Refining & Marketing|$4.3B|$10.91 → $16.63|+52%|+6.73%p|3/0|+10%|-28%|예|
|6|MU|Semiconductors|$1013.8B|$162.94 → $206.89|+27%|+4.91%p|19/1|-10%|-29%|예|
|7|CLF|Steel|$7.8B|$0.36 → $1.00|+181%|+4.72%p|1/0|+24%|-56%|예|
|8|CRGY|Oil & Gas E&P|$4.5B|$2.28 → $2.90|+27%|+4.54%p|7/0|+19%|-6%|-|
|9|GRNT|Oil & Gas E&P|$747M|$0.64 → $0.89|+38%|+4.33%p|1/0|+15%|-17%|-|
|10|CODI|Conglomerates|$779M|$0.28 → $0.67|+139%|+3.76%p|4/1|+4%|-56%|예|
|11|ECHO|Telecom Services|$25.1B|$10.38 → $13.43|+29%|+3.54%p|1/0|-6%|-27%|-|
|12|FRO|Oil & Gas Midstream|$11.2B|$3.53 → $5.24|+48%|+3.40%p|4/1|+30%|-13%|예|
|13|BP|Oil & Gas Integrated|$127.2B|$4.12 → $5.77|+40%|+3.34%p|8/0|+12%|-20%|예|
|14|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.04%p|1/0|-5%|-63%|예|
|15|DHT|Oil & Gas Midstream|$3.8B|$1.80 → $2.50|+39%|+3.01%p|2/0|+27%|-9%|예|
|16|TRLV|Drug Manufacturers - Specialty & Generic|$2.1B|$0.24 → $0.56|+132%|+2.94%p|1/0|+26%|-46%|예|
|17|CMRC|Software - Application|$315M|$0.47 → $0.58|+22%|+2.77%p|4/0|+46%|+19%|-|
|18|INDV|Drug Manufacturers - Specialty & Generic|$4.1B|$3.92 → $4.88|+25%|+2.77%p|3/0|-14%|-31%|예|
|19|JXN|Insurance - Life|$8.8B|$28.02 → $31.63|+13%|+2.76%p|1/0|+12%|-1%|예|
|20|AXTI|Semiconductor Equipment & Materials|$3.7B|$0.75 → $2.25|+199%|+2.62%p|1/0|+8%|-64%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$2.0B|$0.30 → $1.38|+361%|+1.75%p|1/0|-30%|-85%|예|
|2|SPCX|Aerospace & Defense|$1947.0B|$0.65 → $2.25|+245%|+1.08%p|4/0|+25%|-64%|예|
|3|AXTI|Semiconductor Equipment & Materials|$3.7B|$0.75 → $2.25|+199%|+2.62%p|1/0|+8%|-64%|예|
|4|DK|Oil & Gas Refining & Marketing|$4.8B|$3.05 → $9.03|+196%|+7.70%p|4/0|+20%|-60%|예|
|5|CLF|Steel|$7.8B|$0.36 → $1.00|+181%|+4.72%p|1/0|+24%|-56%|예|
|6|DEC|Oil & Gas Integrated|$990M|$2.69 → $7.40|+175%|+32.87%p|2/0|+8%|-61%|예|
|7|CVI|Oil & Gas Refining & Marketing|$6.2B|$1.74 → $4.55|+161%|+4.54%p|4/0|+82%|-30%|예|
|8|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.04%p|1/0|-5%|-63%|예|
|9|CODI|Conglomerates|$779M|$0.28 → $0.67|+139%|+3.76%p|4/1|+4%|-56%|예|
|10|PBF|Oil & Gas Refining & Marketing|$9.8B|$7.74 → $18.51|+139%|+12.97%p|3/1|+34%|-44%|예|
|11|TXO|Oil & Gas E&P|$779M|$0.88 → $1.92|+119%|+7.44%p|1/0|+6%|-52%|예|
|12|CBRL|Restaurants|$1.5B|$1.16 → $2.20|+90%|+1.56%p|3/0|+29%|-32%|예|
|13|SMTC|Semiconductors|$12.7B|$3.90 → $6.67|+71%|+2.04%p|1/0|-2%|-43%|예|
|14|PUBM|Software - Application|$795M|$0.49 → $0.81|+67%|+1.86%p|5/0|+42%|-15%|예|
|15|FSLY|Software - Application|$3.5B|$0.40 → $0.64|+62%|+1.12%p|7/0|+14%|-30%|예|
|16|TEAM|Software - Application|$56.0B|$1.37 → $2.19|+60%|+0.37%p|1/0|+176%|+73%|예|
|17|OSCR|Healthcare Plans|$10.4B|$1.49 → $2.22|+49%|+2.17%p|6/0|+16%|-22%|예|
|18|FRO|Oil & Gas Midstream|$11.2B|$3.53 → $5.24|+48%|+3.40%p|4/1|+30%|-13%|예|
|19|TTMI|Electronic Components|$10.1B|$5.40 → $7.86|+46%|+2.57%p|4/0|-34%|-55%|예|
|20|VSEC|Aerospace & Defense|$4.4B|$5.68 → $8.26|+45%|+1.65%p|2/1|-21%|-46%|-|

전체 결과: `data/processed/revision_screen/20261021T050029Z_39546929296-1.json.gz`
