# 이익 예상치 상향 스크리너

최신 시도: 2026-10-02 00:01 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-02 00:01 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7675|7672|3|0|0|
|EPS 예상치|3230|2412|818|0|0|
|업종(후보)|105|105|0|0|0|
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
- **Semiconductor Equipment & Materials** 6곳: FORM, ACMR, AXTI, KLIC, UCTT, AEHR
- **Software - Application** 5곳: TEAM, FSLY, MNDY, PUBM, SPT
- **Banks - Regional** 5곳: CIB, CLBK, HBT, AMTB, VBNK
- **Oil & Gas Midstream** 5곳: FRO, KNTK, SUNC, DHT, TNK
- **Computer Hardware** 4곳: DELL, STX, WDC, P
- **Medical Care Facilities** 4곳: THC, LFST, AVAH, AGL
- **Oil & Gas E&P** 4곳: MGY, TALO, KOS, TXO
- **Software - Infrastructure** 4곳: PRGS, PGY, SABR, RPAY
- **Aerospace & Defense** 3곳: ARXS, VSEC, SPCX
- **Biotechnology** 3곳: CORT, BLTE, URGN
- **Auto Parts** 3곳: MBLY, DAN, DCH
- **Credit Services** 3곳: BFH, AGM, ECPG

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|TALO|Oil & Gas E&P|$2.7B|$0.04 → $1.66|기저 작음|+9.84%p|2/0|+20%|-97%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.5B|$2.06 → $7.85|+282%|+7.97%p|6/0|+36%|-64%|예|
|3|PBF|Oil & Gas Refining & Marketing|$9.5B|$6.34 → $12.38|+95%|+7.49%p|4/0|+61%|-18%|예|
|4|MPC|Oil & Gas Refining & Marketing|$115.7B|$23.93 → $47.13|+97%|+5.62%p|12/0|+48%|-25%|예|
|5|RPAY|Software - Infrastructure|$321M|$0.97 → $1.16|+20%|+5.28%p|2/1|-15%|-29%|-|
|6|PARR|Oil & Gas Refining & Marketing|$4.2B|$10.00 → $13.84|+38%|+4.56%p|4/1|+40%|+1%|예|
|7|VLO|Oil & Gas Refining & Marketing|$115.6B|$21.14 → $38.04|+80%|+4.20%p|7/1|+45%|-20%|예|
|8|DINO|Oil & Gas Refining & Marketing|$19.7B|$7.40 → $11.82|+60%|+3.98%p|9/2|+48%|-7%|예|
|9|AGL|Medical Care Facilities|$1.3B|$-0.62 → $2.40|적자→흑자|+3.79%p|6/0|-28%|미산출|-|
|10|SUNC|Oil & Gas Midstream|$3.8B|$9.70 → $12.34|+27%|+3.58%p|1/0|+7%|-16%|-|
|11|SPT|Software - Application|$602M|$1.20 → $1.54|+28%|+3.42%p|9/0|+21%|-6%|-|
|12|CODI|Conglomerates|$814M|$0.28 → $0.64|+130%|+3.37%p|4/1|+3%|-55%|예|
|13|URGN|Biotechnology|$2.0B|$1.44 → $2.79|+94%|+3.35%p|5/0|+7%|-45%|-|
|14|PGY|Software - Infrastructure|$1.4B|$3.57 → $4.13|+16%|+3.33%p|7/0|-3%|-16%|-|
|15|PSX|Oil & Gas Refining & Marketing|$104.8B|$17.40 → $25.76|+48%|+3.19%p|15/1|+45%|-2%|예|
|16|NBR|Oil & Gas Drilling|$1.2B|$1.11 → $3.61|+224%|+3.14%p|1/0|+0%|-69%|예|
|17|TXO|Oil & Gas E&P|$774M|$0.89 → $1.31|+47%|+3.01%p|1/0|+10%|-25%|-|
|18|DAN|Auto Parts|$2.9B|$3.38 → $4.19|+24%|+3.00%p|2/1|+10%|-11%|예|
|19|TRLV|Drug Manufacturers - Specialty & Generic|$2.1B|$0.24 → $0.56|+132%|+2.87%p|1/0|+12%|-52%|예|
|20|CIB|Banks - Regional|$21.3B|$9.00 → $11.58|+29%|+2.86%p|4/0|+17%|-9%|-|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$3.3B|$0.30 → $1.38|+361%|+1.07%p|1/0|+42%|-69%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.5B|$2.06 → $7.85|+282%|+7.97%p|6/0|+36%|-64%|예|
|3|NBR|Oil & Gas Drilling|$1.2B|$1.11 → $3.61|+224%|+3.14%p|1/0|+0%|-69%|예|
|4|AXTI|Semiconductor Equipment & Materials|$5.4B|$0.75 → $2.25|+199%|+1.82%p|4/0|+37%|-54%|예|
|5|CORT|Biotechnology|$12.2B|$1.63 → $4.40|+170%|+2.45%p|2/0|+28%|-53%|-|
|6|BLTE|Biotechnology|$6.7B|$0.94 → $2.26|+139%|+0.79%p|1/0|+16%|-52%|예|
|7|CODI|Conglomerates|$814M|$0.28 → $0.64|+130%|+3.37%p|4/1|+3%|-55%|예|
|8|MPC|Oil & Gas Refining & Marketing|$115.7B|$23.93 → $47.13|+97%|+5.62%p|12/0|+48%|-25%|예|
|9|PBF|Oil & Gas Refining & Marketing|$9.5B|$6.34 → $12.38|+95%|+7.49%p|4/0|+61%|-18%|예|
|10|URGN|Biotechnology|$2.0B|$1.44 → $2.79|+94%|+3.35%p|5/0|+7%|-45%|-|
|11|CBRL|Restaurants|$1.2B|$1.16 → $2.14|+85%|+1.88%p|2/0|-2%|-47%|예|
|12|VLO|Oil & Gas Refining & Marketing|$115.6B|$21.14 → $38.04|+80%|+4.20%p|7/1|+45%|-20%|예|
|13|CLBK|Banks - Regional|$2.9B|$0.35 → $0.63|+79%|+2.57%p|1/0|+15%|미산출|예|
|14|PUBM|Software - Application|$856M|$0.49 → $0.81|+67%|+1.73%p|5/0|+38%|-17%|예|
|15|DINO|Oil & Gas Refining & Marketing|$19.7B|$7.40 → $11.82|+60%|+3.98%p|9/2|+48%|-7%|예|
|16|FSLY|Software - Application|$4.1B|$0.39 → $0.63|+60%|+0.91%p|10/0|+42%|-11%|예|
|17|TEAM|Software - Application|$46.5B|$1.39 → $2.19|+57%|+0.43%p|4/1|+114%|+36%|-|
|18|UCTT|Semiconductor Equipment & Materials|$3.6B|$3.77 → $5.87|+56%|+2.67%p|4/0|-24%|-51%|예|
|19|CLF|Steel|$6.2B|$0.50 → $0.77|+54%|+2.49%p|4/1|+12%|-28%|예|
|20|SMTC|Semiconductors|$16.9B|$3.89 → $5.86|+51%|+1.09%p|13/0|+32%|-12%|예|

전체 결과: `data/processed/revision_screen/20261001T150156Z_36880974655-1.json.gz`
