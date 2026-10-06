# 이익 예상치 상향 스크리너

최신 시도: 2026-10-06 15:31 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-06 15:31 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7671|7669|2|0|0|
|EPS 예상치|3284|2428|856|0|0|
|업종(후보)|109|109|0|0|0|
|주가 비교(상위)|31|31|0|0|0|

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
- **Software - Infrastructure** 5곳: BLSH, PGY, PRGS, SABR, RPAY
- **Electronic Components** 4곳: CLS, JBL, TTMI, LFUS
- **Oil & Gas E&P** 4곳: TALO, NOG, KOS, TXO
- **Steel** 3곳: NUE, CLF, TX
- **Medical Care Facilities** 3곳: THC, AVAH, AGL
- **Biotechnology** 3곳: CORT, BLTE, URGN
- **Auto Parts** 3곳: MBLY, DAN, DCH
- **Credit Services** 3곳: BFH, AGM, ECPG

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|PBF|Oil & Gas Refining & Marketing|$10.0B|$6.21 → $17.66|+184%|+13.60%p|4/0|+59%|-44%|예|
|2|TALO|Oil & Gas E&P|$2.8B|$-0.09 → $1.66|적자→흑자|+10.31%p|5/0|+20%|미산출|예|
|3|DK|Oil & Gas Refining & Marketing|$4.6B|$1.86 → $8.26|+345%|+8.49%p|6/0|+34%|-70%|예|
|4|MPC|Oil & Gas Refining & Marketing|$126.5B|$23.99 → $50.69|+111%|+6.16%p|12/0|+54%|-27%|예|
|5|RPAY|Software - Infrastructure|$344M|$0.97 → $1.16|+20%|+4.95%p|2/1|-0%|-17%|-|
|6|TX|Steel|$11.4B|$5.02 → $7.65|+52%|+4.54%p|3/0|+35%|-11%|예|
|7|MU|Semiconductors|$1201.6B|$163.35 → $206.68|+26%|+4.07%p|4/1|+12%|-11%|예|
|8|SUNC|Oil & Gas Midstream|$3.7B|$9.70 → $12.34|+27%|+3.72%p|1/0|+8%|-15%|-|
|9|AGL|Medical Care Facilities|$1.4B|$-0.62 → $2.36|적자→흑자|+3.53%p|6/0|-25%|미산출|-|
|10|SPT|Software - Application|$617M|$1.20 → $1.54|+28%|+3.35%p|9/0|+27%|-1%|-|
|11|CLF|Steel|$7.0B|$0.45 → $0.86|+91%|+3.34%p|1/0|+28%|-33%|예|
|12|UCTT|Semiconductor Equipment & Materials|$3.3B|$3.94 → $6.39|+62%|+3.31%p|4/0|-27%|-55%|예|
|13|URGN|Biotechnology|$2.1B|$1.44 → $2.79|+94%|+3.17%p|5/0|+12%|-42%|-|
|14|PGY|Software - Infrastructure|$1.5B|$3.57 → $4.13|+16%|+3.07%p|7/0|+8%|-7%|-|
|15|TXO|Oil & Gas E&P|$771M|$0.89 → $1.31|+47%|+3.00%p|1/0|+6%|-28%|-|
|16|TRLV|Drug Manufacturers - Specialty & Generic|$2.1B|$0.24 → $0.56|+132%|+2.98%p|1/0|+20%|-48%|예|
|17|NBR|Oil & Gas Drilling|$1.3B|$1.57 → $4.00|+155%|+2.93%p|1/0|+3%|-60%|예|
|18|DAN|Auto Parts|$3.0B|$3.37 → $4.19|+24%|+2.90%p|2/1|+10%|-12%|예|
|19|BP|Oil & Gas Integrated|$114.9B|$4.07 → $5.29|+30%|+2.74%p|6/1|+14%|-12%|예|
|20|TNK|Oil & Gas Midstream|$3.6B|$8.07 → $10.90|+35%|+2.73%p|3/1|+44%|+7%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$3.4B|$0.30 → $1.38|+361%|+1.04%p|1/0|+54%|-67%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.6B|$1.86 → $8.26|+345%|+8.49%p|6/0|+34%|-70%|예|
|3|SPCX|Aerospace & Defense|$2254.0B|$0.64 → $1.94|+204%|+0.76%p|3/0|+15%|-62%|예|
|4|AXTI|Semiconductor Equipment & Materials|$5.7B|$0.75 → $2.25|+199%|+1.73%p|1/0|+44%|-52%|예|
|5|PBF|Oil & Gas Refining & Marketing|$10.0B|$6.21 → $17.66|+184%|+13.60%p|4/0|+59%|-44%|예|
|6|CORT|Biotechnology|$13.2B|$1.63 → $4.40|+170%|+2.27%p|2/0|+31%|-51%|-|
|7|NBR|Oil & Gas Drilling|$1.3B|$1.57 → $4.00|+155%|+2.93%p|1/0|+3%|-60%|예|
|8|BLTE|Biotechnology|$6.4B|$0.94 → $2.26|+139%|+0.83%p|5/2|+4%|-56%|예|
|9|MPC|Oil & Gas Refining & Marketing|$126.5B|$23.99 → $50.69|+111%|+6.16%p|12/0|+54%|-27%|예|
|10|URGN|Biotechnology|$2.1B|$1.44 → $2.79|+94%|+3.17%p|5/0|+12%|-42%|-|
|11|CLF|Steel|$7.0B|$0.45 → $0.86|+91%|+3.34%p|1/0|+28%|-33%|예|
|12|CBRL|Restaurants|$1.3B|$1.16 → $2.12|+83%|+1.71%p|3/0|+16%|-37%|예|
|13|CLBK|Banks - Regional|$3.1B|$0.35 → $0.63|+79%|+2.46%p|1/0|+20%|미산출|예|
|14|PUBM|Software - Application|$847M|$0.49 → $0.81|+67%|+1.75%p|5/0|+41%|-15%|예|
|15|UCTT|Semiconductor Equipment & Materials|$3.3B|$3.94 → $6.39|+62%|+3.31%p|4/0|-27%|-55%|예|
|16|FSLY|Software - Application|$4.1B|$0.39 → $0.63|+60%|+0.91%p|6/0|+32%|-18%|예|
|17|TEAM|Software - Application|$49.8B|$1.39 → $2.19|+57%|+0.40%p|1/0|+130%|+47%|-|
|18|TX|Steel|$11.4B|$5.02 → $7.65|+52%|+4.54%p|3/0|+35%|-11%|예|
|19|SMTC|Semiconductors|$18.0B|$3.89 → $5.86|+51%|+1.02%p|13/0|+50%|-1%|예|
|20|TXO|Oil & Gas E&P|$771M|$0.89 → $1.31|+47%|+3.00%p|1/0|+6%|-28%|-|

전체 결과: `data/processed/revision_screen/20261006T063159Z_37424027804-1.json.gz`
