# 이익 예상치 상향 스크리너

최신 시도: 2026-11-07 10:03 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-11-07 10:03 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7626|7626|0|0|0|
|EPS 예상치|3182|2393|789|0|0|
|업종(후보)|111|111|0|0|0|
|주가 비교(상위)|28|28|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 17곳: COP, EOG, OXY, FANG, PR, OVV, APA, SM, CHRD, MTDR, MUR, CRGY, NOG, BKV, REPX, TXO, GRNT
- **Oil & Gas Integrated** 11곳: XOM, CVX, SHEL, TTE, PBR, BP, EQNR, E, CVE, EC, DEC
- **Semiconductors** 10곳: NVDA, MU, MPWR, CBRS, SWKS, LSCC, SMTC, SIMO, MXL, SKHY
- **Oil & Gas Refining & Marketing** 9곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR, DKL
- **Oil & Gas Midstream** 6곳: VG, FRO, INSW, STNG, DHT, TNK
- **Computer Hardware** 5곳: DELL, SNDK, STX, WDC, SMCI
- **Software - Application** 5곳: TEAM, U, MNDY, FSLY, SPT
- **Communication Equipment** 4곳: HPE, LITE, CIEN, HLIT
- **Semiconductor Equipment & Materials** 3곳: LRCX, ACMR, UCTT
- **Steel** 3곳: NUE, STLD, CLF
- **Electronics & Computer Distribution** 3곳: SNX, ARW, SCSC
- **Banks - Regional** 3곳: HBT, BSVN, SUPV

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$898M|$2.42 → $7.40|+206%|+39.23%p|2/0|-8%|-70%|-|
|2|PBF|Oil & Gas Refining & Marketing|$8.0B|$8.97 → $18.56|+107%|+14.26%p|3/1|+11%|-46%|예|
|3|CLF|Steel|$6.5B|$0.59 → $1.71|+189%|+9.73%p|3/0|-8%|-68%|예|
|4|DK|Oil & Gas Refining & Marketing|$3.9B|$3.21 → $9.32|+190%|+9.56%p|7/1|+7%|-63%|예|
|5|DINO|Oil & Gas Refining & Marketing|$16.7B|$9.00 → $17.90|+99%|+9.16%p|12/0|+20%|-40%|예|
|6|SMCI|Computer Hardware|$18.9B|$3.86 → $6.04|+56%|+7.58%p|5/0|-13%|-44%|예|
|7|TXO|Oil & Gas E&P|$728M|$0.97 → $1.96|+102%|+7.56%p|3/0|-8%|-54%|예|
|8|CRGY|Oil & Gas E&P|$5.4B|$2.27 → $3.08|+36%|+7.24%p|10/0|-4%|-29%|-|
|9|DHT|Oil & Gas Midstream|$3.3B|$1.81 → $3.24|+79%|+6.93%p|3/0|+9%|-39%|예|
|10|GRNT|Oil & Gas E&P|$698M|$0.64 → $1.00|+57%|+6.87%p|3/0|-4%|-39%|-|
|11|SKHY|Semiconductors|$898.0B|$33.62 → $42.30|+26%|+6.81%p|3/0|-10%|-29%|예|
|12|TNK|Oil & Gas Midstream|$3.0B|$9.12 → $14.45|+58%|+6.22%p|2/0|+6%|-33%|-|
|13|UCTT|Semiconductor Equipment & Materials|$2.0B|$3.94 → $6.49|+65%|+6.20%p|4/0|-57%|-74%|예|
|14|MU|Semiconductors|$780.7B|$166.89 → $207.76|+24%|+5.92%p|18/2|-25%|-40%|예|
|15|FRO|Oil & Gas Midstream|$10.1B|$3.72 → $6.24|+68%|+5.56%p|4/1|+12%|-33%|예|
|16|TBLA|Internet Content & Information|$533M|$0.23 → $0.33|+41%|+4.73%p|3/1|-47%|-62%|예|
|17|VSNT|Entertainment|$4.6B|$6.69 → $8.25|+23%|+4.62%p|1/0|-12%|-29%|-|
|18|TTMI|Electronic Components|$7.0B|$5.40 → $8.34|+54%|+4.41%p|4/0|-55%|-71%|예|
|19|WDC|Computer Hardware|$98.7B|$29.34 → $40.40|+38%|+4.20%p|19/0|-38%|-55%|예|
|20|SPT|Software - Application|$651M|$1.19 → $1.63|+37%|+4.01%p|9/0|+4%|-24%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|SPCX|Aerospace & Defense|$1823.5B|$0.57 → $4.03|+608%|+2.58%p|14/0|-7%|-87%|예|
|2|DEC|Oil & Gas Integrated|$898M|$2.42 → $7.40|+206%|+39.23%p|2/0|-8%|-70%|-|
|3|DK|Oil & Gas Refining & Marketing|$3.9B|$3.21 → $9.32|+190%|+9.56%p|7/1|+7%|-63%|예|
|4|CLF|Steel|$6.5B|$0.59 → $1.71|+189%|+9.73%p|3/0|-8%|-68%|예|
|5|GKOS|Medical Devices|$13.3B|$0.50 → $1.40|+179%|+0.40%p|10/0|+22%|-56%|예|
|6|CODI|Conglomerates|$851M|$0.28 → $0.67|+139%|+3.45%p|4/1|+4%|-56%|예|
|7|CVI|Oil & Gas Refining & Marketing|$3.8B|$1.91 → $4.55|+138%|+6.92%p|4/0|+28%|-46%|예|
|8|PBF|Oil & Gas Refining & Marketing|$8.0B|$8.97 → $18.56|+107%|+14.26%p|3/1|+11%|-46%|예|
|9|TXO|Oil & Gas E&P|$728M|$0.97 → $1.96|+102%|+7.56%p|3/0|-8%|-54%|예|
|10|DHT|Oil & Gas Midstream|$3.3B|$1.81 → $3.24|+79%|+6.93%p|3/0|+9%|-39%|예|
|11|TEAM|Software - Application|$38.9B|$1.22 → $2.19|+79%|+0.63%p|2/0|+23%|-31%|예|
|12|SMTC|Semiconductors|$9.6B|$3.92 → $6.67|+70%|+2.67%p|14/0|-34%|-61%|예|
|13|FRO|Oil & Gas Midstream|$10.1B|$3.72 → $6.24|+68%|+5.56%p|4/1|+12%|-33%|예|
|14|MXL|Semiconductors|$4.5B|$2.58 → $4.30|+66%|+3.49%p|10/0|-41%|-64%|예|
|15|UCTT|Semiconductor Equipment & Materials|$2.0B|$3.94 → $6.49|+65%|+6.20%p|4/0|-57%|-74%|예|
|16|FSLY|Software - Application|$2.6B|$0.40 → $0.64|+62%|+1.55%p|7/0|-33%|-59%|예|
|17|TNK|Oil & Gas Midstream|$3.0B|$9.12 → $14.45|+58%|+6.22%p|2/0|+6%|-33%|-|
|18|GRNT|Oil & Gas E&P|$698M|$0.64 → $1.00|+57%|+6.87%p|3/0|-4%|-39%|-|
|19|SMCI|Computer Hardware|$18.9B|$3.86 → $6.04|+56%|+7.58%p|5/0|-13%|-44%|예|
|20|TTMI|Electronic Components|$7.0B|$5.40 → $8.34|+54%|+4.41%p|4/0|-55%|-71%|예|

전체 결과: `data/processed/revision_screen/20261107T010314Z_42321498938-1.json.gz`
