# 이익 예상치 상향 스크리너

최신 시도: 2026-09-26 22:37 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-09-26 22:37 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7676|7672|4|0|0|
|EPS 예상치|3241|2413|828|0|0|
|업종(후보)|100|100|0|0|0|
|주가 비교(상위)|30|30|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas Refining & Marketing** 9곳: VLO, MPC, PSX, DINO, SUN, PBF, CVI, DK, PARR
- **Oil & Gas Midstream** 6곳: FRO, KNTK, SUNC, DHT, TNK, LPG
- **Semiconductors** 5곳: NVDA, INTC, LSCC, SMTC, MXL
- **Semiconductor Equipment & Materials** 5곳: ACMR, AXTI, KLIC, UCTT, AEHR
- **Computer Hardware** 4곳: DELL, STX, WDC, P
- **Banks - Regional** 4곳: CIB, HBT, CLBK, AMTB
- **Medical Care Facilities** 4곳: THC, LFST, AVAH, AGL
- **Oil & Gas E&P** 4곳: MGY, TALO, KOS, TXO
- **Software - Application** 4곳: FSLY, MNDY, PUBM, SPT
- **Aerospace & Defense** 3곳: ARXS, VSEC, SPCX
- **Biotechnology** 3곳: CORT, BLTE, URGN
- **Auto Parts** 3곳: MBLY, DAN, DCH
- **Credit Services** 3곳: BFH, AGM, ECPG
- **Software - Infrastructure** 3곳: PGY, SABR, RPAY

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AMCX|Entertainment|$502M|$1.48 → $2.84|+92%|+11.17%p|7/0|+21%|-37%|-|
|2|TALO|Oil & Gas E&P|$2.7B|$-0.04 → $1.66|적자→흑자|+10.33%p|2/0|+24%|미산출|예|
|3|DK|Oil & Gas Refining & Marketing|$4.2B|$2.06 → $7.85|+282%|+8.54%p|6/0|+42%|-63%|예|
|4|PBF|Oil & Gas Refining & Marketing|$8.7B|$6.34 → $12.38|+95%|+8.19%p|4/0|+71%|-12%|예|
|5|MPC|Oil & Gas Refining & Marketing|$110.5B|$23.93 → $47.13|+97%|+5.90%p|12/0|+55%|-21%|예|
|6|RPAY|Software - Infrastructure|$334M|$0.97 → $1.16|+20%|+5.09%p|2/1|+6%|-12%|-|
|7|PARR|Oil & Gas Refining & Marketing|$3.9B|$10.00 → $13.84|+38%|+4.95%p|4/1|+42%|+2%|예|
|8|VLO|Oil & Gas Refining & Marketing|$111.5B|$21.14 → $38.04|+80%|+4.37%p|7/1|+49%|-17%|예|
|9|DINO|Oil & Gas Refining & Marketing|$19.0B|$7.40 → $11.82|+60%|+4.15%p|9/2|+56%|-2%|예|
|10|AGL|Medical Care Facilities|$1.4B|$-0.62 → $2.40|적자→흑자|+3.74%p|6/0|-32%|미산출|-|
|11|TNK|Oil & Gas Midstream|$3.3B|$7.47 → $10.90|+46%|+3.64%p|3/1|+38%|-5%|-|
|12|SPT|Software - Application|$578M|$1.20 → $1.54|+28%|+3.58%p|9/0|+28%|-1%|-|
|13|SUNC|Oil & Gas Midstream|$3.9B|$9.70 → $12.34|+27%|+3.46%p|1/0|+14%|-10%|-|
|14|PGY|Software - Infrastructure|$1.5B|$3.54 → $4.15|+17%|+3.45%p|7/0|+11%|-5%|-|
|15|URGN|Biotechnology|$2.0B|$1.44 → $2.79|+94%|+3.28%p|5/0|+20%|-38%|-|
|16|CODI|Conglomerates|$846M|$0.28 → $0.64|+130%|+3.24%p|4/1|+8%|-53%|예|
|17|LPG|Oil & Gas Midstream|$2.3B|$3.01 → $4.68|+56%|+3.13%p|2/1|+48%|-5%|예|
|18|NBR|Oil & Gas Drilling|$1.2B|$1.11 → $3.61|+224%|+3.07%p|1/0|-2%|-70%|예|
|19|PSX|Oil & Gas Refining & Marketing|$102.5B|$17.28 → $24.90|+44%|+2.98%p|15/1|+49%|+3%|예|
|20|DAN|Auto Parts|$2.9B|$3.38 → $4.19|+24%|+2.96%p|2/1|-4%|-22%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$3.4B|$0.30 → $1.38|+361%|+1.04%p|1/0|+14%|-75%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.2B|$2.06 → $7.85|+282%|+8.54%p|6/0|+42%|-63%|예|
|3|NBR|Oil & Gas Drilling|$1.2B|$1.11 → $3.61|+224%|+3.07%p|1/0|-2%|-70%|예|
|4|AXTI|Semiconductor Equipment & Materials|$5.2B|$0.75 → $2.25|+199%|+1.90%p|4/0|+12%|-62%|예|
|5|CORT|Biotechnology|$12.6B|$1.63 → $4.40|+170%|+2.39%p|2/0|+33%|-51%|-|
|6|IPI|Agricultural Inputs|$458M|$0.57 → $1.41|+148%|+2.48%p|2/0|-2%|-60%|예|
|7|BLTE|Biotechnology|$6.7B|$0.94 → $2.26|+139%|+0.79%p|1/0|+12%|-53%|예|
|8|CODI|Conglomerates|$846M|$0.28 → $0.64|+130%|+3.24%p|4/1|+8%|-53%|예|
|9|MPC|Oil & Gas Refining & Marketing|$110.5B|$23.93 → $47.13|+97%|+5.90%p|12/0|+55%|-21%|예|
|10|PBF|Oil & Gas Refining & Marketing|$8.7B|$6.34 → $12.38|+95%|+8.19%p|4/0|+71%|-12%|예|
|11|URGN|Biotechnology|$2.0B|$1.44 → $2.79|+94%|+3.28%p|5/0|+20%|-38%|-|
|12|AMCX|Entertainment|$502M|$1.48 → $2.84|+92%|+11.17%p|7/0|+21%|-37%|-|
|13|VLO|Oil & Gas Refining & Marketing|$111.5B|$21.14 → $38.04|+80%|+4.37%p|7/1|+49%|-17%|예|
|14|CLBK|Banks - Regional|$1.2B|$0.35 → $0.63|+79%|+2.46%p|1/0|+20%|미산출|예|
|15|CBRL|Restaurants|$1.2B|$1.16 → $1.96|+69%|+1.54%p|2/0|-2%|-42%|-|
|16|PUBM|Software - Application|$847M|$0.49 → $0.81|+67%|+1.75%p|5/0|+47%|-12%|예|
|17|DINO|Oil & Gas Refining & Marketing|$19.0B|$7.40 → $11.82|+60%|+4.15%p|9/2|+56%|-2%|예|
|18|FSLY|Software - Application|$4.0B|$0.39 → $0.63|+60%|+0.94%p|10/0|+46%|-9%|예|
|19|UCTT|Semiconductor Equipment & Materials|$3.5B|$3.77 → $5.87|+56%|+2.70%p|4/0|-35%|-58%|예|
|20|LPG|Oil & Gas Midstream|$2.3B|$3.01 → $4.68|+56%|+3.13%p|2/1|+48%|-5%|예|

전체 결과: `data/processed/revision_screen/20260926T133740Z_36245680144-1.json.gz`
