# 이익 예상치 상향 스크리너

최신 시도: 2026-11-10 16:30 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-11-10 16:30 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7625|7625|0|0|0|
|EPS 예상치|3205|2404|801|0|0|
|업종(후보)|115|115|0|0|0|
|주가 비교(상위)|28|28|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 18곳: COP, EOG, OXY, FANG, PR, OVV, APA, CHRD, SM, MTDR, MUR, CRGY, TALO, NOG, BKV, REPX, TXO, GRNT
- **Semiconductors** 11곳: NVDA, SKHY, MU, MPWR, CBRS, SWKS, LSCC, SMTC, SIMO, MXL, LASR
- **Oil & Gas Integrated** 10곳: XOM, CVX, SHEL, TTE, BP, EQNR, E, CVE, EC, DEC
- **Oil & Gas Refining & Marketing** 9곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR, DKL
- **Oil & Gas Midstream** 7곳: VG, CQP, FRO, INSW, STNG, DHT, TNK
- **Computer Hardware** 5곳: DELL, SNDK, STX, WDC, SMCI
- **Communication Equipment** 4곳: HPE, LITE, CIEN, HLIT
- **Software - Application** 4곳: U, MNDY, SPT, CMRC
- **Electronics & Computer Distribution** 4곳: SNX, ARW, NSIT, SCSC
- **Steel** 3곳: NUE, STLD, CLF
- **Semiconductor Equipment & Materials** 3곳: ACMR, UCTT, COHU
- **Banks - Regional** 3곳: HBT, BSVN, SUPV

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$913M|$2.42 → $7.63|+216%|+40.37%p|2/0|-11%|-72%|예|
|2|PBF|Oil & Gas Refining & Marketing|$8.2B|$9.19 → $19.43|+111%|+14.72%p|3/1|-1%|-53%|예|
|3|CMRC|Software - Application|$306M|$0.31 → $0.72|+132%|+11.14%p|4/0|+70%|-27%|-|
|4|DK|Oil & Gas Refining & Marketing|$3.9B|$3.71 → $10.46|+182%|+10.38%p|7/1|-3%|-66%|예|
|5|SMCI|Computer Hardware|$18.9B|$3.86 → $6.76|+75%|+10.15%p|5/0|-24%|-57%|예|
|6|CLF|Steel|$7.0B|$0.59 → $1.71|+189%|+9.09%p|4/0|+0%|-65%|예|
|7|DINO|Oil & Gas Refining & Marketing|$16.9B|$9.00 → $17.85|+98%|+8.87%p|12/0|+14%|-43%|예|
|8|CRGY|Oil & Gas E&P|$5.3B|$2.27 → $3.18|+40%|+8.30%p|11/0|-9%|-35%|-|
|9|TXO|Oil & Gas E&P|$730M|$0.97 → $1.94|+100%|+7.38%p|3/0|-9%|-54%|-|
|10|DHT|Oil & Gas Midstream|$3.3B|$1.81 → $3.23|+79%|+6.93%p|3/0|+10%|-39%|예|
|11|SKHY|Semiconductors|$947.6B|$33.62 → $42.30|+26%|+6.46%p|3/0|-13%|-31%|예|
|12|GRNT|Oil & Gas E&P|$748M|$0.63 → $1.00|+57%|+6.40%p|3/0|+11%|-29%|-|
|13|TNK|Oil & Gas Midstream|$3.0B|$9.12 → $14.45|+58%|+6.26%p|2/0|+5%|-34%|-|
|14|AMC|Entertainment|$3.0B|$-0.12 → $0.08|적자→흑자|+6.13%p|2/0|+34%|미산출|-|
|15|FRO|Oil & Gas Midstream|$9.9B|$3.72 → $6.24|+68%|+5.70%p|4/1|+12%|-33%|예|
|16|MU|Semiconductors|$829.5B|$166.89 → $207.76|+24%|+5.58%p|18/2|-20%|-35%|예|
|17|UCTT|Semiconductor Equipment & Materials|$2.2B|$3.94 → $6.49|+65%|+5.56%p|4/0|-49%|-69%|예|
|18|NMM|Marine Shipping|$2.5B|$17.33 → $21.48|+24%|+4.89%p|3/1|+6%|-14%|예|
|19|SPT|Software - Application|$654M|$1.19 → $1.68|+41%|+4.41%p|9/0|+16%|-18%|예|
|20|BP|Oil & Gas Integrated|$114.8B|$4.21 → $6.03|+43%|+4.09%p|11/1|+4%|-28%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$913M|$2.42 → $7.63|+216%|+40.37%p|2/0|-11%|-72%|예|
|2|SPCX|Aerospace & Defense|$1929.5B|$1.32 → $4.04|+207%|+1.92%p|14/1|-3%|-68%|예|
|3|CLF|Steel|$7.0B|$0.59 → $1.71|+189%|+9.09%p|4/0|+0%|-65%|예|
|4|DK|Oil & Gas Refining & Marketing|$3.9B|$3.71 → $10.46|+182%|+10.38%p|7/1|-3%|-66%|예|
|5|GKOS|Medical Devices|$14.1B|$0.50 → $1.40|+179%|+0.38%p|10/0|+28%|-54%|예|
|6|CVI|Oil & Gas Refining & Marketing|$4.3B|$1.91 → $4.46|+133%|+6.51%p|4/0|+12%|-52%|-|
|7|CMRC|Software - Application|$306M|$0.31 → $0.72|+132%|+11.14%p|4/0|+70%|-27%|-|
|8|PBF|Oil & Gas Refining & Marketing|$8.2B|$9.19 → $19.43|+111%|+14.72%p|3/1|-1%|-53%|예|
|9|TXO|Oil & Gas E&P|$730M|$0.97 → $1.94|+100%|+7.38%p|3/0|-9%|-54%|-|
|10|DHT|Oil & Gas Midstream|$3.3B|$1.81 → $3.23|+79%|+6.93%p|3/0|+10%|-39%|예|
|11|SMCI|Computer Hardware|$18.9B|$3.86 → $6.76|+75%|+10.15%p|5/0|-24%|-57%|예|
|12|SMTC|Semiconductors|$10.9B|$3.92 → $6.67|+70%|+2.36%p|14/0|-17%|-51%|예|
|13|FRO|Oil & Gas Midstream|$9.9B|$3.72 → $6.24|+68%|+5.70%p|4/1|+12%|-33%|예|
|14|MXL|Semiconductors|$5.1B|$2.58 → $4.30|+66%|+3.07%p|10/0|-25%|-55%|예|
|15|TALO|Oil & Gas E&P|$2.4B|$1.13 → $1.88|+66%|+5.13%p|4/2|-6%|-43%|-|
|16|UCTT|Semiconductor Equipment & Materials|$2.2B|$3.94 → $6.49|+65%|+5.56%p|4/0|-49%|-69%|예|
|17|TNK|Oil & Gas Midstream|$3.0B|$9.12 → $14.45|+58%|+6.26%p|2/0|+5%|-34%|-|
|18|GRNT|Oil & Gas E&P|$748M|$0.63 → $1.00|+57%|+6.40%p|3/0|+11%|-29%|-|
|19|TTMI|Electronic Components|$7.9B|$5.40 → $8.34|+54%|+3.90%p|4/0|-46%|-65%|예|
|20|ZYME|Biotechnology|$2.2B|$0.83 → $1.21|+47%|+1.26%p|3/1|+24%|-16%|-|

전체 결과: `data/processed/revision_screen/20261110T073052Z_42775409704-1.json.gz`
