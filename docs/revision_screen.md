# 이익 예상치 상향 스크리너

최신 시도: 2026-10-25 13:54 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-25 13:54 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7635|7635|0|0|0|
|EPS 예상치|3185|2403|782|0|0|
|업종(후보)|97|97|0|0|0|
|주가 비교(상위)|30|30|0|0|0|

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
- **Software - Application** 4곳: TEAM, MNDY, FSLY, PUBM
- **Oil & Gas Midstream** 4곳: VG, FRO, INSW, DHT
- **Steel** 3곳: NUE, STLD, CLF
- **Semiconductor Equipment & Materials** 3곳: ACMR, AXTI, ICHR
- **Banks - Regional** 3곳: HBT, AMTB, BSVN

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$1.0B|$2.69 → $7.40|+175%|+32.08%p|2/0|+16%|-58%|예|
|2|PBF|Oil & Gas Refining & Marketing|$9.0B|$7.74 → $18.56|+140%|+14.20%p|3/1|+21%|-49%|예|
|3|KOS|Oil & Gas E&P|$1.7B|$0.23 → $0.47|+101%|+8.18%p|1/0|+18%|-41%|예|
|4|DK|Oil & Gas Refining & Marketing|$4.6B|$3.05 → $9.09|+198%|+8.11%p|4/0|+16%|-61%|예|
|5|CLF|Steel|$7.9B|$0.36 → $1.46|+309%|+7.93%p|1/0|+14%|-72%|예|
|6|TXO|Oil & Gas E&P|$787M|$0.88 → $1.92|+119%|+7.36%p|1/0|+10%|-50%|예|
|7|PARR|Oil & Gas Refining & Marketing|$3.9B|$11.34 → $16.35|+44%|+6.49%p|3/0|-2%|-32%|예|
|8|SMCI|Computer Hardware|$21.6B|$3.86 → $5.59|+45%|+5.25%p|8/0|+10%|-24%|예|
|9|CRGY|Oil & Gas E&P|$5.4B|$2.21 → $2.92|+32%|+5.13%p|7/0|+32%|-0%|-|
|10|MU|Semiconductors|$992.9B|$162.94 → $206.89|+27%|+5.01%p|19/1|-2%|-23%|예|
|11|CODI|Conglomerates|$783M|$0.28 → $0.67|+139%|+3.75%p|4/1|+4%|-57%|예|
|12|TTMI|Electronic Components|$8.4B|$5.40 → $8.34|+54%|+3.67%p|4/0|-35%|-58%|예|
|13|WDC|Computer Hardware|$128.6B|$27.15 → $39.55|+46%|+3.61%p|2/1|-31%|-53%|예|
|14|FRO|Oil & Gas Midstream|$11.8B|$3.53 → $5.24|+48%|+3.23%p|4/1|+37%|-8%|예|
|15|BP|Oil & Gas Integrated|$132.2B|$4.12 → $5.74|+40%|+3.17%p|8/0|+21%|-13%|예|
|16|TRLV|Drug Manufacturers - Specialty & Generic|$2.0B|$0.24 → $0.56|+132%|+3.04%p|1/0|+25%|-46%|예|
|17|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.00%p|1/0|+3%|-60%|예|
|18|AXTI|Semiconductor Equipment & Materials|$3.4B|$0.75 → $2.25|+199%|+2.88%p|1/0|+9%|-64%|예|
|19|DHT|Oil & Gas Midstream|$4.0B|$1.80 → $2.50|+39%|+2.85%p|2/0|+34%|-3%|예|
|20|INDV|Drug Manufacturers - Specialty & Generic|$4.1B|$3.92 → $4.88|+25%|+2.79%p|3/0|-14%|-31%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|SPCX|Aerospace & Defense|$2003.1B|$0.65 → $4.05|+521%|+2.31%p|4/0|+30%|-79%|예|
|2|CLF|Steel|$7.9B|$0.36 → $1.46|+309%|+7.93%p|1/0|+14%|-72%|예|
|3|AXTI|Semiconductor Equipment & Materials|$3.4B|$0.75 → $2.25|+199%|+2.88%p|1/0|+9%|-64%|예|
|4|DK|Oil & Gas Refining & Marketing|$4.6B|$3.05 → $9.09|+198%|+8.11%p|4/0|+16%|-61%|예|
|5|DEC|Oil & Gas Integrated|$1.0B|$2.69 → $7.40|+175%|+32.08%p|2/0|+16%|-58%|예|
|6|CVI|Oil & Gas Refining & Marketing|$5.8B|$1.74 → $4.55|+161%|+4.83%p|4/0|+71%|-35%|예|
|7|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.00%p|1/0|+3%|-60%|예|
|8|PBF|Oil & Gas Refining & Marketing|$9.0B|$7.74 → $18.56|+140%|+14.20%p|3/1|+21%|-49%|예|
|9|CODI|Conglomerates|$783M|$0.28 → $0.67|+139%|+3.75%p|4/1|+4%|-57%|예|
|10|TXO|Oil & Gas E&P|$787M|$0.88 → $1.92|+119%|+7.36%p|1/0|+10%|-50%|예|
|11|CBRL|Restaurants|$1.5B|$1.16 → $2.20|+90%|+1.54%p|3/0|+29%|-32%|예|
|12|TEAM|Software - Application|$57.6B|$1.23 → $2.19|+78%|+0.42%p|1/0|+137%|+33%|예|
|13|SMTC|Semiconductors|$12.3B|$3.90 → $6.67|+71%|+2.10%p|1/0|+9%|-36%|예|
|14|PUBM|Software - Application|$785M|$0.49 → $0.81|+67%|+1.89%p|5/0|+35%|-19%|예|
|15|MXL|Semiconductors|$5.8B|$2.58 → $4.30|+66%|+2.71%p|1/0|-2%|-41%|예|
|16|FSLY|Software - Application|$3.9B|$0.40 → $0.64|+62%|+1.01%p|7/0|+22%|-25%|예|
|17|SEI|Oil & Gas Equipment & Services|$5.9B|$2.33 → $3.66|+57%|+2.26%p|3/0|+12%|-29%|-|
|18|TTMI|Electronic Components|$8.4B|$5.40 → $8.34|+54%|+3.67%p|4/0|-35%|-58%|예|
|19|OSCR|Healthcare Plans|$9.6B|$1.49 → $2.22|+49%|+2.36%p|6/0|+9%|-27%|예|
|20|FRO|Oil & Gas Midstream|$11.8B|$3.53 → $5.24|+48%|+3.23%p|4/1|+37%|-8%|예|

전체 결과: `data/processed/revision_screen/20261025T045431Z_40163475107-1.json.gz`
