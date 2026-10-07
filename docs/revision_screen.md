# 이익 예상치 상향 스크리너

최신 시도: 2026-10-07 15:09 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-07 15:09 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7671|7670|1|0|0|
|EPS 예상치|3230|2413|817|0|0|
|업종(후보)|109|109|0|0|0|
|주가 비교(상위)|32|31|1|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas Refining & Marketing** 9곳: MPC, VLO, PSX, DINO, SUN, PBF, CVI, DK, PARR
- **Semiconductors** 6곳: NVDA, MU, INTC, LSCC, SMTC, MXL
- **Semiconductor Equipment & Materials** 6곳: FORM, ACMR, AXTI, KLIC, AEHR, UCTT
- **Banks - Regional** 6곳: CLBK, PEBO, HBT, AMTB, VBNK, BSVN
- **Oil & Gas Integrated** 5곳: SHEL, TTE, BP, EQNR, E
- **Software - Application** 5곳: TEAM, FSLY, MNDY, PUBM, SPT
- **Oil & Gas Midstream** 5곳: FRO, KNTK, SUNC, DHT, TNK
- **Computer Hardware** 4곳: DELL, SNDK, WDC, P
- **Electronic Components** 4곳: CLS, JBL, TTMI, LFUS
- **Software - Infrastructure** 4곳: BLSH, PRGS, SABR, RPAY
- **Oil & Gas E&P** 4곳: TALO, NOG, KOS, TXO
- **Medical Care Facilities** 3곳: THC, AVAH, AGL
- **Biotechnology** 3곳: CORT, BLTE, URGN
- **Auto Parts** 3곳: MBLY, DAN, DCH
- **Credit Services** 3곳: BFH, AGM, ECPG

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|PBF|Oil & Gas Refining & Marketing|$9.8B|$6.21 → $17.66|+184%|+13.81%p|4/0|+56%|-45%|예|
|2|TALO|Oil & Gas E&P|$2.8B|$-0.09 → $1.66|적자→흑자|+10.46%p|5/0|+22%|미산출|예|
|3|DK|Oil & Gas Refining & Marketing|$4.6B|$1.86 → $8.26|+345%|+8.46%p|6/0|+35%|-70%|예|
|4|MPC|Oil & Gas Refining & Marketing|$121.4B|$23.99 → $50.69|+111%|+6.17%p|12/0|+53%|-28%|예|
|5|RPAY|Software - Infrastructure|$338M|$0.97 → $1.16|+20%|+5.04%p|2/1|-6%|-21%|-|
|6|MU|Semiconductors|$1180.8B|$163.35 → $206.33|+26%|+4.11%p|4/1|+5%|-16%|예|
|7|CLF|Steel|$7.0B|$0.43 → $0.93|+114%|+4.03%p|1/0|+30%|-39%|예|
|8|SUNC|Oil & Gas Midstream|$3.7B|$9.70 → $12.34|+27%|+3.65%p|1/0|미확인|미산출|-|
|9|AGL|Medical Care Facilities|$1.4B|$-0.62 → $2.36|적자→흑자|+3.57%p|6/0|-28%|미산출|-|
|10|SPT|Software - Application|$614M|$1.20 → $1.54|+28%|+3.37%p|9/0|+21%|-6%|-|
|11|UCTT|Semiconductor Equipment & Materials|$3.3B|$3.94 → $6.39|+62%|+3.35%p|4/0|-31%|-58%|예|
|12|JXN|Insurance - Life|$9.0B|$26.52 → $30.90|+16%|+3.29%p|4/0|+20%|+3%|예|
|13|URGN|Biotechnology|$2.0B|$1.44 → $2.79|+94%|+3.28%p|5/0|+3%|-47%|-|
|14|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.00%p|1/0|+1%|-60%|예|
|15|TXO|Oil & Gas E&P|$774M|$0.89 → $1.31|+47%|+2.98%p|1/0|+6%|-28%|-|
|16|TRLV|Drug Manufacturers - Specialty & Generic|$2.1B|$0.24 → $0.56|+132%|+2.98%p|1/0|+20%|-48%|예|
|17|DAN|Auto Parts|$3.1B|$3.37 → $4.19|+24%|+2.86%p|2/1|+8%|-13%|예|
|18|TNK|Oil & Gas Midstream|$3.5B|$8.07 → $10.90|+35%|+2.79%p|3/1|+46%|+8%|예|
|19|BP|Oil & Gas Integrated|$115.9B|$4.07 → $5.29|+30%|+2.71%p|6/1|+17%|-10%|예|
|20|INDV|Drug Manufacturers - Specialty & Generic|$4.2B|$3.92 → $4.88|+25%|+2.68%p|3/0|-13%|-30%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$3.0B|$0.30 → $1.38|+361%|+1.18%p|1/0|+21%|-74%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.6B|$1.86 → $8.26|+345%|+8.46%p|6/0|+35%|-70%|예|
|3|SPCX|Aerospace & Defense|$2266.2B|$0.64 → $2.05|+220%|+0.82%p|3/0|+13%|-65%|예|
|4|AXTI|Semiconductor Equipment & Materials|$5.5B|$0.75 → $2.25|+199%|+1.78%p|1/0|+34%|-55%|예|
|5|PBF|Oil & Gas Refining & Marketing|$9.8B|$6.21 → $17.66|+184%|+13.81%p|4/0|+56%|-45%|예|
|6|CORT|Biotechnology|$12.9B|$1.63 → $4.40|+170%|+2.32%p|2/0|+28%|-52%|-|
|7|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.00%p|1/0|+1%|-60%|예|
|8|BLTE|Biotechnology|$6.3B|$0.94 → $2.26|+139%|+0.85%p|5/2|+2%|-58%|예|
|9|CLF|Steel|$7.0B|$0.43 → $0.93|+114%|+4.03%p|1/0|+30%|-39%|예|
|10|MPC|Oil & Gas Refining & Marketing|$121.4B|$23.99 → $50.69|+111%|+6.17%p|12/0|+53%|-28%|예|
|11|URGN|Biotechnology|$2.0B|$1.44 → $2.79|+94%|+3.28%p|5/0|+3%|-47%|-|
|12|CBRL|Restaurants|$1.3B|$1.16 → $2.12|+83%|+1.71%p|3/0|+14%|-38%|예|
|13|CLBK|Banks - Regional|$3.0B|$0.35 → $0.63|+79%|+2.51%p|1/0|+16%|미산출|예|
|14|PUBM|Software - Application|$836M|$0.49 → $0.81|+67%|+1.77%p|5/0|+35%|-19%|예|
|15|UCTT|Semiconductor Equipment & Materials|$3.3B|$3.94 → $6.39|+62%|+3.35%p|4/0|-31%|-58%|예|
|16|FSLY|Software - Application|$4.1B|$0.39 → $0.63|+60%|+0.93%p|6/0|+26%|-22%|예|
|17|TEAM|Software - Application|$49.1B|$1.39 → $2.19|+57%|+0.41%p|1/0|+114%|+36%|-|
|18|SMTC|Semiconductors|$18.4B|$3.89 → $5.86|+51%|+1.00%p|13/0|+43%|-5%|예|
|19|TXO|Oil & Gas E&P|$774M|$0.89 → $1.31|+47%|+2.98%p|1/0|+6%|-28%|-|
|20|OSCR|Healthcare Plans|$10.0B|$1.48 → $2.17|+46%|+2.10%p|6/0|+4%|-29%|예|

전체 결과: `data/processed/revision_screen/20261007T060957Z_37579928333-1.json.gz`
