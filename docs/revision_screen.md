# 이익 예상치 상향 스크리너

기준: 2026-09-25 01:40 KST · 대상 3295개(미국 상장, 시가총액 $300M 이상, 분석가 3명 이상) · 후보 105개 · 조회 실패 1개

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다. 순위는 두 가지다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다. 주가가 비싼 고성장주는 A에서 작게 나오므로 따로 본다.

- **주가 90일**이 EPS 증가율보다 작으면 **PER 변화**가 음수다. 시장이 이익 증가를 아직 덜 반영했을 수 있다는 뜻이며 저평가의 증거는 아니다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다. 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas Refining & Marketing** 9곳: VLO, MPC, PSX, DINO, SUN, PBF, CVI, DK, PARR
- **Oil & Gas Midstream** 6곳: FRO, KNTK, SUNC, DHT, TNK, LPG
- **Semiconductors** 5곳: NVDA, INTC, LSCC, SMTC, MXL
- **Medical Care Facilities** 5곳: THC, LFST, AVAH, AGL, NUTX
- **Software - Application** 5곳: U, FSLY, MNDY, PUBM, SPT
- **Semiconductor Equipment & Materials** 5곳: AXTI, ACMR, KLIC, UCTT, AEHR
- **Computer Hardware** 4곳: DELL, STX, WDC, P
- **Biotechnology** 4곳: INSM, CORT, BLTE, URGN
- **Banks - Regional** 4곳: CIB, HBT, CLBK, AMTB
- **Oil & Gas E&P** 4곳: MGY, TALO, KOS, TXO
- **Steel** 3곳: NUE, CLF, TX
- **Aerospace & Defense** 3곳: ARXS, VSEC, SPCX
- **Auto Parts** 3곳: MBLY, DAN, DCH
- **Credit Services** 3곳: BFH, AGM, ECPG
- **Software - Infrastructure** 3곳: PGY, SABR, RPAY

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AMCX|Entertainment|$494M|$1.48 → $2.76|+86%|+10.62%p|7/0|+19%|-36%|-|
|2|TALO|Oil & Gas E&P|$2.8B|$-0.04 → $1.66|적자→흑자 등|+10.07%p|2/0|+27%|-|예|
|3|DK|Oil & Gas Refining & Marketing|$4.2B|$2.06 → $7.85|+282%|+8.50%p|6/0|+43%|-62%|예|
|4|PBF|Oil & Gas Refining & Marketing|$8.6B|$6.34 → $12.38|+95%|+8.33%p|4/0|+69%|-14%|예|
|5|MPC|Oil & Gas Refining & Marketing|$111.1B|$23.93 → $47.13|+97%|+5.87%p|12/0|+56%|-21%|예|
|6|AGL|Medical Care Facilities|$1.3B|$-0.62 → $3.20|+618%|+5.09%p|6/0|-37%|-|-|
|7|PARR|Oil & Gas Refining & Marketing|$3.9B|$10.00 → $13.84|+38%|+4.94%p|4/1|+42%|+3%|예|
|8|RPAY|Software - Infrastructure|$350M|$0.97 → $1.16|+20%|+4.86%p|2/1|+11%|-8%|-|
|9|TX|Steel|$11.0B|$5.02 → $7.65|+52%|+4.71%p|3/0|+26%|-17%|예|
|10|VLO|Oil & Gas Refining & Marketing|$111.3B|$21.14 → $38.04|+80%|+4.37%p|7/1|+50%|-17%|예|
|11|DINO|Oil & Gas Refining & Marketing|$19.1B|$7.40 → $11.82|+60%|+4.13%p|9/2|+58%|-1%|예|
|12|TNK|Oil & Gas Midstream|$3.3B|$7.47 → $10.90|+46%|+3.62%p|3/1|+40%|-4%|-|
|13|SPT|Software - Application|$590M|$1.20 → $1.54|+28%|+3.50%p|9/0|+30%|+1%|-|
|14|SUNC|Oil & Gas Midstream|$4.0B|$9.70 → $12.34|+27%|+3.41%p|1/0|+17%|-8%|-|
|15|URGN|Biotechnology|$2.0B|$1.44 → $2.79|+94%|+3.31%p|5/0|+19%|-39%|-|
|16|PGY|Software - Infrastructure|$1.5B|$3.54 → $4.15|+17%|+3.28%p|7/0|+17%|-0%|-|
|17|CODI|Conglomerates|$845M|$0.28 → $0.64|+130%|+3.24%p|4/1|+8%|-53%|예|
|18|LPG|Oil & Gas Midstream|$2.3B|$3.01 → $4.68|+56%|+3.08%p|2/1|+54%|-1%|예|
|19|NBR|Oil & Gas Drilling|$1.3B|$1.11 → $3.61|+224%|+3.01%p|1/0|+0%|-69%|예|
|20|PSX|Oil & Gas Refining & Marketing|$104.4B|$17.28 → $24.90|+44%|+2.92%p|15/1|+53%|+6%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$3.2B|$0.30 → $1.38|+361%|+1.11%p|1/0|+6%|-77%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.2B|$2.06 → $7.85|+282%|+8.50%p|6/0|+43%|-62%|예|
|3|NBR|Oil & Gas Drilling|$1.3B|$1.11 → $3.61|+224%|+3.01%p|1/0|+0%|-69%|예|
|4|AXTI|Semiconductor Equipment & Materials|$5.0B|$0.75 → $2.25|+199%|+1.97%p|4/0|+8%|-64%|예|
|5|CORT|Biotechnology|$12.3B|$1.63 → $4.40|+170%|+2.44%p|2/0|+30%|-52%|-|
|6|IPI|Agricultural Inputs|$480M|$0.57 → $1.41|+148%|+2.37%p|2/0|+3%|-58%|예|
|7|BLTE|Biotechnology|$6.7B|$0.94 → $2.26|+139%|+0.79%p|1/0|+12%|-53%|예|
|8|INSM|Biotechnology|$26.1B|$0.33 → $0.77|+130%|+0.36%p|13/3|+16%|-50%|-|
|9|CODI|Conglomerates|$845M|$0.28 → $0.64|+130%|+3.24%p|4/1|+8%|-53%|예|
|10|MPC|Oil & Gas Refining & Marketing|$111.1B|$23.93 → $47.13|+97%|+5.87%p|12/0|+56%|-21%|예|
|11|PBF|Oil & Gas Refining & Marketing|$8.6B|$6.34 → $12.38|+95%|+8.33%p|4/0|+69%|-14%|예|
|12|URGN|Biotechnology|$2.0B|$1.44 → $2.79|+94%|+3.31%p|5/0|+19%|-39%|-|
|13|AMCX|Entertainment|$494M|$1.48 → $2.76|+86%|+10.62%p|7/0|+19%|-36%|-|
|14|VLO|Oil & Gas Refining & Marketing|$111.3B|$21.14 → $38.04|+80%|+4.37%p|7/1|+50%|-17%|예|
|15|CLBK|Banks - Regional|$1.2B|$0.35 → $0.63|+79%|+2.48%p|1/0|+19%|-33%|예|
|16|PUBM|Software - Application|$845M|$0.49 → $0.81|+66%|+1.74%p|5/0|+47%|-12%|예|
|17|DINO|Oil & Gas Refining & Marketing|$19.1B|$7.40 → $11.82|+60%|+4.13%p|9/2|+58%|-1%|예|
|18|FSLY|Software - Application|$4.4B|$0.39 → $0.63|+60%|+0.86%p|10/0|+60%|+0%|예|
|19|UCTT|Semiconductor Equipment & Materials|$3.5B|$3.77 → $5.87|+56%|+2.73%p|4/0|-35%|-58%|예|
|20|LPG|Oil & Gas Midstream|$2.3B|$3.01 → $4.68|+56%|+3.08%p|2/1|+54%|-1%|예|

전체 결과: `data/processed/revision_screen/2026-09-25.json.gz`
