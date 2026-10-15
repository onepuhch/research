# 이익 예상치 상향 스크리너

최신 시도: 2026-10-15 13:51 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-15 13:51 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7653|7652|1|0|0|
|EPS 예상치|3235|2418|817|0|0|
|업종(후보)|103|103|0|0|0|
|주가 비교(상위)|31|31|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 13곳: OXY, PR, APA, SM, CHRD, MTDR, MUR, CRGY, TALO, NOG, KOS, TXO, GRNT
- **Oil & Gas Refining & Marketing** 8곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR
- **Semiconductors** 7곳: NVDA, MU, INTC, ALAB, LSCC, SMTC, MXL
- **Oil & Gas Integrated** 7곳: CVX, SHEL, TTE, BP, EQNR, E, CVE
- **Semiconductor Equipment & Materials** 6곳: FORM, KLIC, ACMR, AXTI, AEHR, ICHR
- **Banks - Regional** 6곳: PEBO, HBT, AMTB, HTB, VBNK, BSVN
- **Computer Hardware** 5곳: DELL, SNDK, STX, WDC, P
- **Software - Application** 4곳: TEAM, FSLY, MNDY, PUBM
- **Software - Infrastructure** 3곳: BLSH, PRGS, RPAY

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|TALO|Oil & Gas E&P|$2.8B|$-0.36 → $1.77|적자→흑자|+12.47%p|5/0|+14%|미산출|예|
|2|PBF|Oil & Gas Refining & Marketing|$10.6B|$7.41 → $17.38|+135%|+11.14%p|3/0|+43%|-39%|-|
|3|DK|Oil & Gas Refining & Marketing|$4.8B|$2.17 → $8.35|+284%|+7.82%p|4/0|+25%|-68%|예|
|4|MPC|Oil & Gas Refining & Marketing|$141.6B|$25.27 → $55.19|+118%|+6.17%p|13/0|+55%|-29%|예|
|5|RPAY|Software - Infrastructure|$353M|$0.97 → $1.16|+20%|+4.82%p|2/1|+3%|-14%|-|
|6|MU|Semiconductors|$1034.3B|$163.35 → $206.33|+26%|+4.70%p|19/1|+8%|-15%|예|
|7|NOG|Oil & Gas E&P|$2.8B|$3.89 → $5.04|+30%|+4.37%p|2/1|+24%|-4%|예|
|8|CLF|Steel|$7.2B|$0.43 → $0.96|+123%|+4.22%p|1/0|+36%|-39%|예|
|9|CODI|Conglomerates|$803M|$0.28 → $0.67|+139%|+3.65%p|4/1|+3%|-57%|예|
|10|TRLV|Drug Manufacturers - Specialty & Generic|$1.9B|$0.24 → $0.56|+132%|+3.18%p|1/0|+13%|-51%|예|
|11|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.11%p|1/0|-7%|-63%|예|
|12|DHT|Oil & Gas Midstream|$4.0B|$1.73 → $2.50|+44%|+3.08%p|2/0|+43%|-1%|-|
|13|FRO|Oil & Gas Midstream|$12.5B|$3.53 → $5.24|+48%|+3.04%p|4/1|+54%|+4%|예|
|14|TXO|Oil & Gas E&P|$790M|$0.88 → $1.31|+49%|+3.03%p|1/0|+11%|-26%|예|
|15|BP|Oil & Gas Integrated|$125.7B|$4.10 → $5.49|+34%|+2.84%p|8/0|+16%|-13%|예|
|16|INDV|Drug Manufacturers - Specialty & Generic|$4.0B|$3.92 → $4.88|+25%|+2.82%p|3/0|-16%|-32%|예|
|17|JXN|Insurance - Life|$8.8B|$28.02 → $31.63|+13%|+2.77%p|4/0|+4%|-8%|예|
|18|BLSH|Software - Infrastructure|$4.6B|$2.53 → $3.27|+29%|+2.44%p|1/0|+36%|+5%|-|
|19|AXTI|Semiconductor Equipment & Materials|$4.0B|$0.75 → $2.25|+199%|+2.43%p|1/0|+34%|-55%|예|
|20|PRGS|Software - Infrastructure|$1.6B|$6.24 → $7.18|+15%|+2.43%p|4/0|-5%|-17%|-|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$2.3B|$0.30 → $1.38|+361%|+1.51%p|1/0|-12%|-81%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.8B|$2.17 → $8.35|+284%|+7.82%p|4/0|+25%|-68%|예|
|3|SPCX|Aerospace & Defense|$2004.6B|$0.65 → $2.08|+218%|+0.94%p|3/0|+23%|-61%|예|
|4|AXTI|Semiconductor Equipment & Materials|$4.0B|$0.75 → $2.25|+199%|+2.43%p|1/0|+34%|-55%|예|
|5|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.11%p|1/0|-7%|-63%|예|
|6|BLTE|Biotechnology|$6.2B|$0.94 → $2.26|+139%|+0.86%p|5/2|+2%|-58%|예|
|7|CODI|Conglomerates|$803M|$0.28 → $0.67|+139%|+3.65%p|4/1|+3%|-57%|예|
|8|PBF|Oil & Gas Refining & Marketing|$10.6B|$7.41 → $17.38|+135%|+11.14%p|3/0|+43%|-39%|-|
|9|CLF|Steel|$7.2B|$0.43 → $0.96|+123%|+4.22%p|1/0|+36%|-39%|예|
|10|CVI|Oil & Gas Refining & Marketing|$6.2B|$1.74 → $3.86|+121%|+3.41%p|2/0|+76%|-20%|예|
|11|CBRL|Restaurants|$1.4B|$1.16 → $2.20|+90%|+1.66%p|3/0|+17%|-38%|예|
|12|PUBM|Software - Application|$804M|$0.49 → $0.81|+67%|+1.84%p|5/0|+39%|-17%|예|
|13|FSLY|Software - Application|$4.0B|$0.39 → $0.64|+63%|+0.99%p|6/0|+21%|-26%|예|
|14|TEAM|Software - Application|$51.8B|$1.36 → $2.19|+60%|+0.40%p|1/0|+119%|+37%|예|
|15|SMTC|Semiconductors|$15.0B|$3.89 → $5.86|+51%|+1.23%p|1/0|+28%|-15%|예|
|16|TXO|Oil & Gas E&P|$790M|$0.88 → $1.31|+49%|+3.03%p|1/0|+11%|-26%|예|
|17|OSCR|Healthcare Plans|$10.6B|$1.49 → $2.22|+49%|+2.13%p|6/0|+18%|-21%|예|
|18|FRO|Oil & Gas Midstream|$12.5B|$3.53 → $5.24|+48%|+3.04%p|4/1|+54%|+4%|예|
|19|ALAB|Semiconductors|$52.1B|$4.37 → $6.40|+47%|+0.68%p|20/0|-1%|-32%|-|
|20|DHT|Oil & Gas Midstream|$4.0B|$1.73 → $2.50|+44%|+3.08%p|2/0|+43%|-1%|-|

전체 결과: `data/processed/revision_screen/20261015T045150Z_38683526891-1.json.gz`
