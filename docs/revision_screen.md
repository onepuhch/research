# 이익 예상치 상향 스크리너

최신 시도: 2026-10-04 15:01 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-04 15:01 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7675|7673|2|0|0|
|EPS 예상치|3237|2414|823|0|0|
|업종(후보)|102|102|0|0|0|
|주가 비교(상위)|32|32|0|0|0|

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
- **Banks - Regional** 6곳: CIB, CLBK, PEBO, HBT, AMTB, VBNK
- **Semiconductor Equipment & Materials** 6곳: FORM, ACMR, AXTI, KLIC, UCTT, AEHR
- **Software - Application** 5곳: TEAM, FSLY, MNDY, PUBM, SPT
- **Oil & Gas Midstream** 5곳: FRO, KNTK, SUNC, DHT, TNK
- **Oil & Gas Integrated** 4곳: SHEL, BP, EQNR, E
- **Medical Care Facilities** 4곳: THC, LFST, AVAH, AGL
- **Oil & Gas E&P** 4곳: MTDR, TALO, KOS, TXO
- **Software - Infrastructure** 4곳: PRGS, PGY, SABR, RPAY
- **Computer Hardware** 3곳: DELL, WDC, P
- **Electronic Components** 3곳: CLS, JBL, LFUS
- **Biotechnology** 3곳: CORT, BLTE, URGN
- **Auto Parts** 3곳: MBLY, DAN, DCH
- **Credit Services** 3곳: BFH, AGM, ECPG

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|PBF|Oil & Gas Refining & Marketing|$9.6B|$6.21 → $17.66|+184%|+14.17%p|4/0|+64%|-42%|예|
|2|TALO|Oil & Gas E&P|$2.8B|$-0.09 → $1.66|적자→흑자|+10.45%p|2/0|+27%|미산출|예|
|3|DK|Oil & Gas Refining & Marketing|$4.5B|$1.86 → $8.26|+345%|+8.63%p|4/0|+40%|-68%|예|
|4|MPC|Oil & Gas Refining & Marketing|$118.6B|$23.99 → $49.60|+107%|+6.06%p|10/0|+57%|-24%|예|
|5|PARR|Oil & Gas Refining & Marketing|$4.2B|$10.02 → $14.84|+48%|+5.75%p|3/1|+38%|-7%|예|
|6|RPAY|Software - Infrastructure|$337M|$0.97 → $1.16|+20%|+5.05%p|2/1|-9%|-24%|-|
|7|DINO|Oil & Gas Refining & Marketing|$20.2B|$7.39 → $12.74|+72%|+4.72%p|5/0|+52%|-12%|예|
|8|VLO|Oil & Gas Refining & Marketing|$117.0B|$21.44 → $40.19|+87%|+4.62%p|9/1|+50%|-20%|예|
|9|MU|Semiconductors|$1214.0B|$163.35 → $205.95|+26%|+3.96%p|2/1|+9%|-13%|예|
|10|AGL|Medical Care Facilities|$1.4B|$-0.62 → $2.40|적자→흑자|+3.59%p|6/0|-22%|미산출|-|
|11|SUNC|Oil & Gas Midstream|$3.9B|$9.70 → $12.34|+27%|+3.48%p|1/0|+12%|-12%|-|
|12|SPT|Software - Application|$611M|$1.20 → $1.54|+28%|+3.38%p|9/0|+22%|-5%|-|
|13|UCTT|Semiconductor Equipment & Materials|$3.3B|$3.94 → $6.39|+62%|+3.38%p|4/0|-31%|-58%|예|
|14|PSX|Oil & Gas Refining & Marketing|$106.1B|$17.40 → $26.21|+51%|+3.33%p|10/0|+49%|-1%|예|
|15|URGN|Biotechnology|$2.0B|$1.44 → $2.79|+94%|+3.28%p|5/0|+11%|-43%|-|
|16|PGY|Software - Infrastructure|$1.5B|$3.57 → $4.13|+16%|+3.15%p|7/0|-4%|-17%|-|
|17|NBR|Oil & Gas Drilling|$1.2B|$1.11 → $3.61|+224%|+3.13%p|1/0|+4%|-68%|예|
|18|TXO|Oil & Gas E&P|$768M|$0.89 → $1.31|+47%|+3.01%p|1/0|+12%|-24%|-|
|19|TRLV|Drug Manufacturers - Specialty & Generic|$2.1B|$0.24 → $0.56|+132%|+2.96%p|1/0|+22%|-48%|예|
|20|DAN|Auto Parts|$3.0B|$3.37 → $4.19|+24%|+2.92%p|2/1|+7%|-14%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$3.5B|$0.30 → $1.38|+361%|+1.01%p|1/0|+48%|-68%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.5B|$1.86 → $8.26|+345%|+8.63%p|4/0|+40%|-68%|예|
|3|NBR|Oil & Gas Drilling|$1.2B|$1.11 → $3.61|+224%|+3.13%p|1/0|+4%|-68%|예|
|4|AXTI|Semiconductor Equipment & Materials|$5.6B|$0.75 → $2.25|+199%|+1.74%p|4/0|+35%|-55%|예|
|5|PBF|Oil & Gas Refining & Marketing|$9.6B|$6.21 → $17.66|+184%|+14.17%p|4/0|+64%|-42%|예|
|6|CORT|Biotechnology|$12.6B|$1.63 → $4.40|+170%|+2.38%p|2/0|+27%|-53%|-|
|7|BLTE|Biotechnology|$6.4B|$0.94 → $2.26|+139%|+0.82%p|5/2|+4%|-57%|예|
|8|MPC|Oil & Gas Refining & Marketing|$118.6B|$23.99 → $49.60|+107%|+6.06%p|10/0|+57%|-24%|예|
|9|URGN|Biotechnology|$2.0B|$1.44 → $2.79|+94%|+3.28%p|5/0|+11%|-43%|-|
|10|VLO|Oil & Gas Refining & Marketing|$117.0B|$21.44 → $40.19|+87%|+4.62%p|9/1|+50%|-20%|예|
|11|CBRL|Restaurants|$1.2B|$1.16 → $2.12|+83%|+1.73%p|3/0|+10%|-40%|예|
|12|CLBK|Banks - Regional|$3.1B|$0.35 → $0.63|+79%|+2.45%p|1/0|+17%|미산출|예|
|13|DINO|Oil & Gas Refining & Marketing|$20.2B|$7.39 → $12.74|+72%|+4.72%p|5/0|+52%|-12%|예|
|14|PUBM|Software - Application|$839M|$0.49 → $0.81|+67%|+1.76%p|5/0|+36%|-18%|예|
|15|UCTT|Semiconductor Equipment & Materials|$3.3B|$3.94 → $6.39|+62%|+3.38%p|4/0|-31%|-58%|예|
|16|CVI|Oil & Gas Refining & Marketing|$5.5B|$2.17 → $3.51|+62%|+2.45%p|3/0|+90%|+17%|-|
|17|FSLY|Software - Application|$4.1B|$0.39 → $0.63|+60%|+0.91%p|6/0|+41%|-12%|예|
|18|TEAM|Software - Application|$47.6B|$1.39 → $2.19|+57%|+0.42%p|4/1|+120%|+40%|-|
|19|CLF|Steel|$6.5B|$0.50 → $0.77|+54%|+2.40%p|4/1|+16%|-25%|예|
|20|SMTC|Semiconductors|$18.2B|$3.89 → $5.86|+51%|+1.01%p|13/0|+40%|-7%|예|

전체 결과: `data/processed/revision_screen/20261004T060125Z_37181539693-1.json.gz`
