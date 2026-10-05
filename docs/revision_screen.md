# 이익 예상치 상향 스크리너

최신 시도: 2026-10-05 14:51 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-05 14:51 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7675|7673|2|0|0|
|EPS 예상치|3238|2415|823|0|0|
|업종(후보)|105|105|0|0|0|
|주가 비교(상위)|33|33|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas Refining & Marketing** 9곳: VLO, MPC, PSX, DINO, SUN, PBF, CVI, DK, PARR
- **Semiconductors** 6곳: NVDA, MU, INTC, LSCC, SMTC, MXL
- **Semiconductor Equipment & Materials** 6곳: FORM, ACMR, AXTI, KLIC, UCTT, AEHR
- **Banks - Regional** 6곳: CLBK, PEBO, HBT, AMTB, VBNK, BSVN
- **Software - Application** 5곳: TEAM, FSLY, MNDY, PUBM, SPT
- **Oil & Gas Midstream** 5곳: FRO, KNTK, SUNC, DHT, TNK
- **Oil & Gas E&P** 5곳: MTDR, TALO, NOG, KOS, TXO
- **Software - Infrastructure** 5곳: BLSH, PRGS, PGY, SABR, RPAY
- **Oil & Gas Integrated** 4곳: SHEL, BP, EQNR, E
- **Medical Care Facilities** 4곳: THC, LFST, AVAH, AGL
- **Computer Hardware** 3곳: DELL, WDC, P
- **Electronic Components** 3곳: CLS, JBL, LFUS
- **Biotechnology** 3곳: CORT, BLTE, URGN
- **Auto Parts** 3곳: MBLY, DAN, DCH
- **Credit Services** 3곳: BFH, AGM, ECPG

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|PBF|Oil & Gas Refining & Marketing|$9.6B|$6.21 → $17.66|+184%|+14.17%p|4/0|+67%|-41%|예|
|2|TALO|Oil & Gas E&P|$2.8B|$-0.09 → $1.66|적자→흑자|+10.45%p|2/0|+24%|미산출|예|
|3|DK|Oil & Gas Refining & Marketing|$4.5B|$1.86 → $8.26|+345%|+8.63%p|5/0|+42%|-68%|예|
|4|MPC|Oil & Gas Refining & Marketing|$118.6B|$23.99 → $49.60|+107%|+6.06%p|11/0|+59%|-23%|예|
|5|RPAY|Software - Infrastructure|$337M|$0.97 → $1.16|+20%|+5.05%p|2/1|-5%|-21%|-|
|6|MU|Semiconductors|$1214.0B|$163.35 → $205.95|+26%|+3.96%p|3/1|+14%|-9%|예|
|7|AGL|Medical Care Facilities|$1.4B|$-0.62 → $2.40|적자→흑자|+3.59%p|6/0|-22%|미산출|-|
|8|SUNC|Oil & Gas Midstream|$3.9B|$9.70 → $12.34|+27%|+3.48%p|1/0|+9%|-15%|-|
|9|SPT|Software - Application|$611M|$1.20 → $1.54|+28%|+3.38%p|9/0|+23%|-4%|-|
|10|UCTT|Semiconductor Equipment & Materials|$3.3B|$3.94 → $6.39|+62%|+3.38%p|4/0|-20%|-51%|예|
|11|URGN|Biotechnology|$2.0B|$1.44 → $2.79|+94%|+3.28%p|5/0|+10%|-44%|-|
|12|PGY|Software - Infrastructure|$1.5B|$3.57 → $4.13|+16%|+3.15%p|7/0|-2%|-15%|-|
|13|NBR|Oil & Gas Drilling|$1.2B|$1.11 → $3.61|+224%|+3.13%p|1/0|+2%|-68%|예|
|14|TXO|Oil & Gas E&P|$768M|$0.89 → $1.31|+47%|+3.01%p|1/0|+8%|-26%|-|
|15|TRLV|Drug Manufacturers - Specialty & Generic|$2.1B|$0.24 → $0.56|+132%|+2.96%p|1/0|+20%|-48%|예|
|16|DAN|Auto Parts|$3.0B|$3.37 → $4.19|+24%|+2.92%p|2/1|+10%|-12%|예|
|17|TNK|Oil & Gas Midstream|$3.6B|$8.07 → $10.90|+35%|+2.74%p|3/1|+49%|+10%|예|
|18|INDV|Drug Manufacturers - Specialty & Generic|$4.2B|$3.92 → $4.88|+25%|+2.70%p|3/0|-12%|-30%|예|
|19|HIPO|Insurance - Property & Casualty|$851M|$2.68 → $3.52|+31%|+2.59%p|4/0|+13%|-14%|예|
|20|PRGS|Software - Infrastructure|$1.5B|$6.24 → $7.17|+15%|+2.53%p|1/0|-6%|-18%|-|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$3.5B|$0.30 → $1.38|+361%|+1.01%p|1/0|+60%|-65%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.5B|$1.86 → $8.26|+345%|+8.63%p|5/0|+42%|-68%|예|
|3|NBR|Oil & Gas Drilling|$1.2B|$1.11 → $3.61|+224%|+3.13%p|1/0|+2%|-68%|예|
|4|AXTI|Semiconductor Equipment & Materials|$5.6B|$0.75 → $2.25|+199%|+1.74%p|1/0|+48%|-51%|예|
|5|PBF|Oil & Gas Refining & Marketing|$9.6B|$6.21 → $17.66|+184%|+14.17%p|4/0|+67%|-41%|예|
|6|CORT|Biotechnology|$12.6B|$1.63 → $4.40|+170%|+2.38%p|2/0|+24%|-54%|-|
|7|BLTE|Biotechnology|$6.4B|$0.94 → $2.26|+139%|+0.82%p|5/2|+1%|-58%|예|
|8|MPC|Oil & Gas Refining & Marketing|$118.6B|$23.99 → $49.60|+107%|+6.06%p|11/0|+59%|-23%|예|
|9|URGN|Biotechnology|$2.0B|$1.44 → $2.79|+94%|+3.28%p|5/0|+10%|-44%|-|
|10|CBRL|Restaurants|$1.2B|$1.16 → $2.12|+83%|+1.73%p|3/0|+13%|-38%|예|
|11|CLBK|Banks - Regional|$3.1B|$0.35 → $0.63|+79%|+2.45%p|1/0|+17%|미산출|예|
|12|PUBM|Software - Application|$839M|$0.49 → $0.81|+67%|+1.76%p|5/0|+38%|-17%|예|
|13|UCTT|Semiconductor Equipment & Materials|$3.3B|$3.94 → $6.39|+62%|+3.38%p|4/0|-20%|-51%|예|
|14|FSLY|Software - Application|$4.1B|$0.39 → $0.63|+60%|+0.91%p|6/0|+39%|-13%|예|
|15|TEAM|Software - Application|$47.6B|$1.39 → $2.19|+57%|+0.42%p|1/0|+113%|+36%|-|
|16|CLF|Steel|$6.5B|$0.50 → $0.77|+54%|+2.40%p|4/1|+19%|-23%|예|
|17|SMTC|Semiconductors|$18.2B|$3.89 → $5.86|+51%|+1.01%p|13/0|+54%|+2%|예|
|18|TXO|Oil & Gas E&P|$768M|$0.89 → $1.31|+47%|+3.01%p|1/0|+8%|-26%|-|
|19|OSCR|Healthcare Plans|$9.5B|$1.48 → $2.17|+46%|+2.20%p|6/0|-1%|-32%|예|
|20|VSEC|Aerospace & Defense|$4.7B|$5.72 → $8.28|+45%|+1.53%p|9/1|-24%|-48%|-|

전체 결과: `data/processed/revision_screen/20261005T055133Z_37269585919-1.json.gz`
