# 이익 예상치 상향 스크리너

최신 시도: 2026-10-17 13:39 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-17 13:39 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7649|7649|0|0|0|
|EPS 예상치|3182|2408|774|0|0|
|업종(후보)|102|102|0|0|0|
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
- **Oil & Gas Integrated** 9곳: CVX, SHEL, TTE, BP, EQNR, E, EC, DEC, PBR-A
- **Oil & Gas Refining & Marketing** 8곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR
- **Semiconductors** 7곳: NVDA, MU, INTC, ALAB, LSCC, SMTC, MXL
- **Computer Hardware** 5곳: DELL, SNDK, STX, WDC, P
- **Semiconductor Equipment & Materials** 5곳: KLIC, ACMR, AXTI, AEHR, ICHR
- **Software - Application** 4곳: TEAM, FSLY, MNDY, PUBM
- **Banks - Regional** 4곳: PEBO, HBT, AMTB, BSVN

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$1.0B|$2.69 → $7.40|+175%|+31.78%p|2/0|+11%|-60%|예|
|2|PBF|Oil & Gas Refining & Marketing|$10.0B|$7.41 → $17.38|+135%|+11.80%p|3/1|+35%|-43%|-|
|3|DK|Oil & Gas Refining & Marketing|$4.7B|$2.17 → $9.55|+339%|+9.63%p|4/0|+21%|-72%|-|
|4|TXO|Oil & Gas E&P|$788M|$0.88 → $1.92|+119%|+7.35%p|1/0|+11%|-49%|예|
|5|MPC|Oil & Gas Refining & Marketing|$134.3B|$25.27 → $55.93|+121%|+6.41%p|12/2|+53%|-31%|예|
|6|ECHO|Telecom Services|$24.8B|$10.38 → $15.70|+51%|+6.23%p|1/0|-7%|-39%|-|
|7|MU|Semiconductors|$994.3B|$163.35 → $206.89|+27%|+4.96%p|19/1|+4%|-18%|예|
|8|CLF|Steel|$6.9B|$0.38 → $0.95|+152%|+4.72%p|1/0|+31%|-48%|예|
|9|NOG|Oil & Gas E&P|$2.9B|$3.89 → $5.03|+29%|+4.18%p|2/1|+28%|-1%|예|
|10|CODI|Conglomerates|$753M|$0.28 → $0.67|+139%|+3.90%p|4/1|-3%|-60%|예|
|11|GRNT|Oil & Gas E&P|$719M|$0.64 → $0.83|+29%|+3.44%p|1/0|+17%|-10%|-|
|12|FRO|Oil & Gas Midstream|$11.7B|$3.53 → $5.24|+48%|+3.26%p|4/1|+44%|-3%|예|
|13|DHT|Oil & Gas Midstream|$3.8B|$1.73 → $2.50|+44%|+3.26%p|2/0|+36%|-6%|예|
|14|TRLV|Drug Manufacturers - Specialty & Generic|$1.9B|$0.24 → $0.56|+132%|+3.17%p|1/0|+14%|-51%|예|
|15|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.11%p|1/0|-7%|-63%|예|
|16|INDV|Drug Manufacturers - Specialty & Generic|$3.8B|$3.92 → $4.88|+25%|+2.97%p|3/0|-20%|-36%|예|
|17|AXTI|Semiconductor Equipment & Materials|$3.4B|$0.75 → $2.25|+199%|+2.91%p|1/0|+12%|-62%|예|
|18|BP|Oil & Gas Integrated|$129.3B|$4.06 → $5.50|+35%|+2.86%p|8/0|+20%|-12%|예|
|19|PBR-A|Oil & Gas Integrated|$159.5B|$3.41 → $4.07|+20%|+2.84%p|2/1|+46%|+22%|예|
|20|JXN|Insurance - Life|$8.8B|$28.02 → $31.63|+13%|+2.76%p|1/0|+4%|-8%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$2.0B|$0.30 → $1.38|+361%|+1.79%p|1/0|-25%|-84%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.7B|$2.17 → $9.55|+339%|+9.63%p|4/0|+21%|-72%|-|
|3|SPCX|Aerospace & Defense|$1924.9B|$0.65 → $2.12|+225%|+1.01%p|4/0|+18%|-64%|예|
|4|AXTI|Semiconductor Equipment & Materials|$3.4B|$0.75 → $2.25|+199%|+2.91%p|1/0|+12%|-62%|예|
|5|DEC|Oil & Gas Integrated|$1.0B|$2.69 → $7.40|+175%|+31.78%p|2/0|+11%|-60%|예|
|6|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.11%p|1/0|-7%|-63%|예|
|7|CLF|Steel|$6.9B|$0.38 → $0.95|+152%|+4.72%p|1/0|+31%|-48%|예|
|8|CVI|Oil & Gas Refining & Marketing|$6.2B|$1.74 → $4.24|+144%|+4.07%p|4/0|+75%|-28%|예|
|9|CODI|Conglomerates|$753M|$0.28 → $0.67|+139%|+3.90%p|4/1|-3%|-60%|예|
|10|PBF|Oil & Gas Refining & Marketing|$10.0B|$7.41 → $17.38|+135%|+11.80%p|3/1|+35%|-43%|-|
|11|TXO|Oil & Gas E&P|$788M|$0.88 → $1.92|+119%|+7.35%p|1/0|+11%|-49%|예|
|12|CBRL|Restaurants|$1.5B|$1.16 → $2.20|+90%|+1.51%p|3/0|+29%|-32%|예|
|13|SMTC|Semiconductors|$12.8B|$3.90 → $6.67|+71%|+2.03%p|1/0|+9%|-36%|예|
|14|PUBM|Software - Application|$758M|$0.49 → $0.81|+67%|+1.95%p|5/0|+31%|-22%|예|
|15|FSLY|Software - Application|$3.6B|$0.40 → $0.64|+62%|+1.10%p|7/0|+8%|-33%|예|
|16|TEAM|Software - Application|$52.6B|$1.37 → $2.19|+59%|+0.39%p|1/0|+123%|+40%|예|
|17|ECHO|Telecom Services|$24.8B|$10.38 → $15.70|+51%|+6.23%p|1/0|-7%|-39%|-|
|18|OSCR|Healthcare Plans|$9.8B|$1.49 → $2.22|+49%|+2.29%p|6/0|+10%|-26%|예|
|19|FRO|Oil & Gas Midstream|$11.7B|$3.53 → $5.24|+48%|+3.26%p|4/1|+44%|-3%|예|
|20|ALAB|Semiconductors|$49.6B|$4.37 → $6.40|+47%|+0.71%p|20/0|-6%|-36%|-|

전체 결과: `data/processed/revision_screen/20261017T043924Z_39003255215-1.json.gz`
