# 이익 예상치 상향 스크리너

최신 시도: 2026-10-23 14:02 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-23 14:02 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7631|7631|0|0|0|
|EPS 예상치|3233|2418|815|0|0|
|업종(후보)|100|100|0|0|0|
|주가 비교(상위)|29|29|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 16곳: COP, OXY, FANG, PR, OVV, APA, AR, SM, CHRD, MTDR, MUR, CRGY, NOG, KOS, TXO, GRNT
- **Oil & Gas Integrated** 8곳: CVX, SHEL, TTE, BP, EQNR, E, EC, DEC
- **Oil & Gas Refining & Marketing** 8곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR
- **Semiconductors** 7곳: NVDA, MU, INTC, ALAB, LSCC, SMTC, MXL
- **Computer Hardware** 6곳: DELL, SNDK, STX, WDC, P, SMCI
- **Software - Application** 5곳: TEAM, MNDY, FSLY, PUBM, CMRC
- **Oil & Gas Midstream** 4곳: VG, FRO, INSW, DHT
- **Steel** 3곳: NUE, STLD, CLF
- **Semiconductor Equipment & Materials** 3곳: ACMR, AXTI, ICHR
- **Banks - Regional** 3곳: HBT, AMTB, BSVN

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$993M|$2.69 → $7.40|+175%|+32.75%p|2/0|+9%|-60%|예|
|2|PBF|Oil & Gas Refining & Marketing|$9.4B|$7.74 → $18.56|+140%|+13.65%p|3/1|+29%|-46%|예|
|3|KOS|Oil & Gas E&P|$1.6B|$0.23 → $0.47|+101%|+8.69%p|1/0|+3%|-49%|예|
|4|CLF|Steel|$7.4B|$0.36 → $1.46|+309%|+8.45%p|1/0|+9%|-73%|예|
|5|DK|Oil & Gas Refining & Marketing|$4.6B|$3.05 → $9.09|+198%|+7.96%p|4/0|+20%|-60%|예|
|6|TXO|Oil & Gas E&P|$770M|$0.88 → $1.92|+119%|+7.52%p|1/0|+6%|-52%|예|
|7|MPC|Oil & Gas Refining & Marketing|$134.1B|$29.19 → $58.44|+100%|+6.37%p|12/2|+48%|-26%|예|
|8|ECHO|Telecom Services|$24.9B|$10.38 → $15.70|+51%|+6.20%p|1/0|-2%|-36%|-|
|9|CRGY|Oil & Gas E&P|$4.4B|$2.21 → $2.90|+31%|+5.15%p|7/0|+18%|-10%|-|
|10|SMCI|Computer Hardware|$21.8B|$3.86 → $5.59|+45%|+5.13%p|8/0|+12%|-23%|예|
|11|MU|Semiconductors|$969.1B|$162.94 → $206.85|+27%|+5.13%p|19/1|-7%|-27%|예|
|12|CODI|Conglomerates|$776M|$0.28 → $0.67|+139%|+3.78%p|4/1|+3%|-57%|예|
|13|FRO|Oil & Gas Midstream|$11.4B|$3.53 → $5.24|+48%|+3.34%p|4/1|+30%|-12%|예|
|14|TTMI|Electronic Components|$7.8B|$5.40 → $7.86|+46%|+3.33%p|4/0|-44%|-61%|예|
|15|BP|Oil & Gas Integrated|$128.9B|$4.12 → $5.74|+40%|+3.25%p|8/0|+14%|-18%|예|
|16|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.13%p|1/0|-7%|-63%|예|
|17|DHT|Oil & Gas Midstream|$3.9B|$1.80 → $2.50|+39%|+2.91%p|2/0|+31%|-6%|예|
|18|AXTI|Semiconductor Equipment & Materials|$3.4B|$0.75 → $2.25|+199%|+2.90%p|1/0|+9%|-64%|예|
|19|TRLV|Drug Manufacturers - Specialty & Generic|$2.1B|$0.24 → $0.56|+132%|+2.90%p|1/0|+31%|-44%|예|
|20|CMRC|Software - Application|$304M|$0.47 → $0.58|+22%|+2.87%p|4/0|+35%|+11%|-|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|SPCX|Aerospace & Defense|$1907.0B|$0.65 → $3.58|+449%|+2.02%p|4/0|+26%|-77%|예|
|2|CLF|Steel|$7.4B|$0.36 → $1.46|+309%|+8.45%p|1/0|+9%|-73%|예|
|3|AXTI|Semiconductor Equipment & Materials|$3.4B|$0.75 → $2.25|+199%|+2.90%p|1/0|+9%|-64%|예|
|4|DK|Oil & Gas Refining & Marketing|$4.6B|$3.05 → $9.09|+198%|+7.96%p|4/0|+20%|-60%|예|
|5|DEC|Oil & Gas Integrated|$993M|$2.69 → $7.40|+175%|+32.75%p|2/0|+9%|-60%|예|
|6|CVI|Oil & Gas Refining & Marketing|$5.9B|$1.74 → $4.55|+161%|+4.79%p|4/0|+75%|-33%|예|
|7|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.13%p|1/0|-7%|-63%|예|
|8|PBF|Oil & Gas Refining & Marketing|$9.4B|$7.74 → $18.56|+140%|+13.65%p|3/1|+29%|-46%|예|
|9|CODI|Conglomerates|$776M|$0.28 → $0.67|+139%|+3.78%p|4/1|+3%|-57%|예|
|10|TXO|Oil & Gas E&P|$770M|$0.88 → $1.92|+119%|+7.52%p|1/0|+6%|-52%|예|
|11|CBRL|Restaurants|$1.5B|$1.16 → $2.20|+90%|+1.55%p|3/0|+25%|-34%|예|
|12|SMTC|Semiconductors|$11.7B|$3.90 → $6.67|+71%|+2.21%p|1/0|-1%|-42%|예|
|13|PUBM|Software - Application|$782M|$0.49 → $0.81|+67%|+1.89%p|5/0|+37%|-18%|예|
|14|FSLY|Software - Application|$3.6B|$0.40 → $0.64|+62%|+1.10%p|7/0|+11%|-32%|예|
|15|TEAM|Software - Application|$56.5B|$1.37 → $2.19|+60%|+0.37%p|1/0|+157%|+61%|예|
|16|SEI|Oil & Gas Equipment & Services|$5.9B|$2.33 → $3.66|+57%|+2.26%p|3/0|+8%|-31%|-|
|17|ECHO|Telecom Services|$24.9B|$10.38 → $15.70|+51%|+6.20%p|1/0|-2%|-36%|-|
|18|OSCR|Healthcare Plans|$10.3B|$1.49 → $2.22|+49%|+2.19%p|6/0|+18%|-21%|예|
|19|FRO|Oil & Gas Midstream|$11.4B|$3.53 → $5.24|+48%|+3.34%p|4/1|+30%|-12%|예|
|20|TTMI|Electronic Components|$7.8B|$5.40 → $7.86|+46%|+3.33%p|4/0|-44%|-61%|예|

전체 결과: `data/processed/revision_screen/20261023T050252Z_39903386847-1.json.gz`
