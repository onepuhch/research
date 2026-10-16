# 이익 예상치 상향 스크리너

최신 시도: 2026-10-16 13:42 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-16 13:42 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7649|7649|0|0|0|
|EPS 예상치|3195|2413|782|0|0|
|업종(후보)|102|102|0|0|0|
|주가 비교(상위)|31|31|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 14곳: OXY, FANG, PR, APA, SM, CHRD, MTDR, MUR, CRGY, NOG, KRP, KOS, TXO, GRNT
- **Oil & Gas Integrated** 9곳: CVX, SHEL, TTE, BP, EQNR, E, CVE, EC, DEC
- **Oil & Gas Refining & Marketing** 8곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR
- **Semiconductors** 7곳: NVDA, MU, INTC, ALAB, LSCC, SMTC, MXL
- **Banks - Regional** 6곳: PEBO, HBT, AMTB, HTB, VBNK, BSVN
- **Computer Hardware** 5곳: DELL, SNDK, STX, WDC, P
- **Semiconductor Equipment & Materials** 5곳: KLIC, ACMR, AXTI, AEHR, ICHR
- **Software - Application** 4곳: TEAM, FSLY, MNDY, PUBM
- **Software - Infrastructure** 3곳: BLSH, PRGS, RPAY

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$996M|$2.58 → $5.84|+126%|+22.58%p|2/0|+8%|-52%|예|
|2|PBF|Oil & Gas Refining & Marketing|$10.3B|$7.41 → $17.38|+135%|+11.46%p|3/1|+39%|-41%|-|
|3|DK|Oil & Gas Refining & Marketing|$4.7B|$2.17 → $8.35|+284%|+8.03%p|4/0|+22%|-68%|예|
|4|MPC|Oil & Gas Refining & Marketing|$133.9B|$25.27 → $55.93|+121%|+6.43%p|13/0|+53%|-31%|예|
|5|RPAY|Software - Infrastructure|$369M|$0.97 → $1.16|+20%|+4.60%p|2/1|+8%|-10%|-|
|6|NOG|Oil & Gas E&P|$2.7B|$3.89 → $5.04|+30%|+4.46%p|2/1|+22%|-6%|예|
|7|MU|Semiconductors|$1053.6B|$163.35 → $204.47|+25%|+4.42%p|19/1|+10%|-12%|-|
|8|CLF|Steel|$6.9B|$0.43 → $0.96|+123%|+4.38%p|1/0|+31%|-41%|예|
|9|GRNT|Oil & Gas E&P|$671M|$0.64 → $0.83|+29%|+3.68%p|3/1|+9%|-16%|-|
|10|CODI|Conglomerates|$799M|$0.28 → $0.67|+139%|+3.67%p|4/1|+3%|-57%|예|
|11|DHT|Oil & Gas Midstream|$3.8B|$1.73 → $2.50|+44%|+3.28%p|2/0|+35%|-7%|-|
|12|FRO|Oil & Gas Midstream|$11.7B|$3.53 → $5.24|+48%|+3.26%p|4/1|+44%|-3%|예|
|13|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.19%p|1/0|-9%|-64%|예|
|14|TRLV|Drug Manufacturers - Specialty & Generic|$2.0B|$0.24 → $0.56|+132%|+3.08%p|1/0|+17%|-50%|예|
|15|TXO|Oil & Gas E&P|$787M|$0.88 → $1.31|+49%|+3.04%p|1/0|+11%|-26%|예|
|16|BP|Oil & Gas Integrated|$124.8B|$4.06 → $5.50|+35%|+2.97%p|8/0|+16%|-15%|예|
|17|INDV|Drug Manufacturers - Specialty & Generic|$4.0B|$3.92 → $4.88|+25%|+2.87%p|3/0|-17%|-33%|예|
|18|JXN|Insurance - Life|$8.9B|$28.02 → $31.63|+13%|+2.74%p|1/0|+5%|-7%|예|
|19|AXTI|Semiconductor Equipment & Materials|$3.8B|$0.75 → $2.25|+199%|+2.59%p|1/0|+26%|-58%|예|
|20|BLSH|Software - Infrastructure|$4.8B|$2.53 → $3.27|+29%|+2.32%p|1/0|+42%|+10%|-|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$2.3B|$0.30 → $1.38|+361%|+1.56%p|1/0|-15%|-82%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.7B|$2.17 → $8.35|+284%|+8.03%p|4/0|+22%|-68%|예|
|3|SPCX|Aerospace & Defense|$1959.1B|$0.65 → $2.08|+218%|+0.96%p|4/0|+20%|-62%|예|
|4|AXTI|Semiconductor Equipment & Materials|$3.8B|$0.75 → $2.25|+199%|+2.59%p|1/0|+26%|-58%|예|
|5|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.19%p|1/0|-9%|-64%|예|
|6|BLTE|Biotechnology|$6.1B|$0.94 → $2.26|+139%|+0.86%p|5/2|+2%|-58%|예|
|7|CODI|Conglomerates|$799M|$0.28 → $0.67|+139%|+3.67%p|4/1|+3%|-57%|예|
|8|PBF|Oil & Gas Refining & Marketing|$10.3B|$7.41 → $17.38|+135%|+11.46%p|3/1|+39%|-41%|-|
|9|CVI|Oil & Gas Refining & Marketing|$6.2B|$1.74 → $4.03|+131%|+3.70%p|2/0|+76%|-24%|예|
|10|DEC|Oil & Gas Integrated|$996M|$2.58 → $5.84|+126%|+22.58%p|2/0|+8%|-52%|예|
|11|CLF|Steel|$6.9B|$0.43 → $0.96|+123%|+4.38%p|1/0|+31%|-41%|예|
|12|CBRL|Restaurants|$1.5B|$1.16 → $2.20|+90%|+1.54%p|3/0|+26%|-34%|예|
|13|PUBM|Software - Application|$812M|$0.49 → $0.81|+67%|+1.82%p|5/0|+40%|-16%|예|
|14|FSLY|Software - Application|$4.0B|$0.39 → $0.64|+63%|+0.99%p|7/0|+21%|-26%|예|
|15|TEAM|Software - Application|$55.0B|$1.37 → $2.19|+59%|+0.38%p|1/0|+133%|+46%|예|
|16|SMTC|Semiconductors|$13.5B|$3.90 → $5.86|+50%|+1.35%p|1/0|+15%|-23%|예|
|17|TXO|Oil & Gas E&P|$787M|$0.88 → $1.31|+49%|+3.04%p|1/0|+11%|-26%|예|
|18|OSCR|Healthcare Plans|$10.3B|$1.49 → $2.22|+49%|+2.19%p|6/0|+15%|-23%|예|
|19|FRO|Oil & Gas Midstream|$11.7B|$3.53 → $5.24|+48%|+3.26%p|4/1|+44%|-3%|예|
|20|ALAB|Semiconductors|$52.4B|$4.37 → $6.40|+47%|+0.67%p|20/0|-0%|-32%|-|

전체 결과: `data/processed/revision_screen/20261016T044212Z_38851792506-1.json.gz`
