# 이익 예상치 상향 스크리너

최신 시도: 2026-10-09 15:23 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-09 15:23 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7666|7664|2|0|0|
|EPS 예상치|3266|2428|838|0|0|
|업종(후보)|106|106|0|0|0|
|주가 비교(상위)|32|32|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas Refining & Marketing** 8곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR
- **Banks - Regional** 7곳: CLBK, HBT, AMTB, HTB, VBNK, PEBO, BSVN
- **Semiconductors** 6곳: NVDA, MU, INTC, LSCC, SMTC, MXL
- **Semiconductor Equipment & Materials** 6곳: FORM, AXTI, ACMR, KLIC, UCTT, AEHR
- **Oil & Gas Integrated** 5곳: SHEL, TTE, BP, EQNR, E
- **Software - Application** 5곳: TEAM, FSLY, MNDY, PUBM, SPT
- **Oil & Gas E&P** 5곳: CHRD, TALO, NOG, KOS, TXO
- **Oil & Gas Midstream** 4곳: FRO, KNTK, DHT, TNK
- **Software - Infrastructure** 4곳: BLSH, PRGS, SABR, RPAY
- **Computer Hardware** 3곳: SNDK, WDC, P
- **Steel** 3곳: NUE, CLF, TX
- **Electronic Components** 3곳: CLS, JBL, TTMI
- **Medical Care Facilities** 3곳: THC, AVAH, AGL
- **Auto Parts** 3곳: MBLY, DAN, DCH
- **Credit Services** 3곳: BFH, AGM, ECPG

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|PBF|Oil & Gas Refining & Marketing|$10.6B|$6.21 → $17.66|+184%|+12.81%p|4/0|+68%|-41%|예|
|2|TALO|Oil & Gas E&P|$2.8B|$-0.09 → $1.66|적자→흑자|+10.35%p|5/0|+26%|미산출|예|
|3|DK|Oil & Gas Refining & Marketing|$4.7B|$1.94 → $7.79|+301%|+7.63%p|6/0|+38%|-66%|-|
|4|MPC|Oil & Gas Refining & Marketing|$135.3B|$23.99 → $50.69|+111%|+5.76%p|12/0|+63%|-23%|예|
|5|RPAY|Software - Infrastructure|$341M|$0.97 → $1.16|+20%|+4.98%p|2/1|-5%|-21%|-|
|6|TXO|Oil & Gas E&P|$795M|$0.88 → $1.56|+79%|+4.79%p|1/0|+10%|-38%|예|
|7|JXN|Insurance - Life|$9.0B|$26.52 → $32.08|+21%|+4.18%p|4/0|+14%|-6%|예|
|8|MU|Semiconductors|$1169.9B|$163.35 → $206.33|+26%|+4.15%p|4/1|+6%|-16%|예|
|9|CLF|Steel|$7.0B|$0.43 → $0.93|+114%|+4.05%p|1/0|+30%|-40%|예|
|10|UCTT|Semiconductor Equipment & Materials|$3.0B|$3.94 → $6.39|+62%|+3.63%p|4/0|-36%|-61%|예|
|11|TX|Steel|$11.1B|$5.68 → $7.70|+36%|+3.57%p|3/0|+28%|-6%|예|
|12|AGL|Medical Care Facilities|$1.4B|$-0.62 → $2.36|적자→흑자|+3.52%p|6/0|-26%|미산출|-|
|13|SPT|Software - Application|$671M|$1.20 → $1.54|+28%|+3.08%p|9/0|+34%|+4%|-|
|14|TRLV|Drug Manufacturers - Specialty & Generic|$2.0B|$0.24 → $0.56|+132%|+3.06%p|1/0|+20%|-48%|예|
|15|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+2.98%p|1/0|-1%|-61%|예|
|16|DAN|Auto Parts|$3.1B|$3.37 → $4.19|+24%|+2.80%p|2/1|+6%|-14%|-|
|17|BP|Oil & Gas Integrated|$119.4B|$4.07 → $5.33|+31%|+2.73%p|6/1|+18%|-10%|예|
|18|INDV|Drug Manufacturers - Specialty & Generic|$4.2B|$3.92 → $4.88|+25%|+2.72%p|3/0|-12%|-30%|예|
|19|TNK|Oil & Gas Midstream|$3.7B|$8.07 → $10.90|+35%|+2.65%p|3/1|+47%|+9%|예|
|20|CLBK|Banks - Regional|$3.0B|$0.35 → $0.63|+79%|+2.54%p|1/0|+14%|미산출|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$2.8B|$0.30 → $1.38|+361%|+1.24%p|1/0|+20%|-74%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.7B|$1.94 → $7.79|+301%|+7.63%p|6/0|+38%|-66%|-|
|3|SPCX|Aerospace & Defense|$2115.4B|$0.68 → $2.04|+201%|+0.85%p|3/0|+10%|-63%|예|
|4|AXTI|Semiconductor Equipment & Materials|$4.7B|$0.75 → $2.25|+199%|+2.09%p|1/0|+25%|-58%|예|
|5|PBF|Oil & Gas Refining & Marketing|$10.6B|$6.21 → $17.66|+184%|+12.81%p|4/0|+68%|-41%|예|
|6|CORT|Biotechnology|$12.8B|$1.63 → $4.40|+170%|+2.34%p|2/0|+29%|-52%|-|
|7|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+2.98%p|1/0|-1%|-61%|예|
|8|BLTE|Biotechnology|$6.1B|$0.94 → $2.26|+139%|+0.86%p|5/2|+2%|-57%|예|
|9|CLF|Steel|$7.0B|$0.43 → $0.93|+114%|+4.05%p|1/0|+30%|-40%|예|
|10|MPC|Oil & Gas Refining & Marketing|$135.3B|$23.99 → $50.69|+111%|+5.76%p|12/0|+63%|-23%|예|
|11|CBRL|Restaurants|$1.2B|$1.16 → $2.12|+83%|+1.74%p|3/0|+10%|-40%|예|
|12|CLBK|Banks - Regional|$3.0B|$0.35 → $0.63|+79%|+2.54%p|1/0|+14%|미산출|예|
|13|TXO|Oil & Gas E&P|$795M|$0.88 → $1.56|+79%|+4.79%p|1/0|+10%|-38%|예|
|14|PUBM|Software - Application|$851M|$0.49 → $0.81|+67%|+1.74%p|5/0|+38%|-17%|예|
|15|UCTT|Semiconductor Equipment & Materials|$3.0B|$3.94 → $6.39|+62%|+3.63%p|4/0|-36%|-61%|예|
|16|FSLY|Software - Application|$4.0B|$0.39 → $0.63|+60%|+0.93%p|6/0|+29%|-19%|예|
|17|TEAM|Software - Application|$51.5B|$1.39 → $2.19|+57%|+0.39%p|1/0|+129%|+46%|-|
|18|SMTC|Semiconductors|$17.5B|$3.89 → $5.86|+51%|+1.05%p|13/0|+38%|-9%|예|
|19|OSCR|Healthcare Plans|$10.2B|$1.48 → $2.17|+46%|+2.06%p|6/0|+8%|-26%|예|
|20|VSEC|Aerospace & Defense|$4.8B|$5.68 → $8.28|+46%|+1.53%p|9/1|-20%|-45%|-|

전체 결과: `data/processed/revision_screen/20261009T062316Z_37892786686-1.json.gz`
