# 이익 예상치 상향 스크리너

최신 시도: 2026-10-14 14:03 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-14 14:03 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7648|7648|0|0|0|
|EPS 예상치|3204|2414|790|0|0|
|업종(후보)|102|102|0|0|0|
|주가 비교(상위)|33|33|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 10곳: PR, APA, SM, CHRD, MTDR, TALO, NOG, KOS, TXO, GRNT
- **Oil & Gas Refining & Marketing** 8곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR
- **Semiconductors** 6곳: NVDA, MU, INTC, LSCC, SMTC, MXL
- **Oil & Gas Integrated** 6곳: CVX, SHEL, TTE, BP, EQNR, E
- **Semiconductor Equipment & Materials** 6곳: FORM, ACMR, KLIC, AXTI, AEHR, ICHR
- **Banks - Regional** 6곳: HBT, AMTB, HTB, VBNK, PEBO, BSVN
- **Computer Hardware** 5곳: DELL, SNDK, STX, WDC, P
- **Software - Application** 5곳: TEAM, FSLY, MNDY, PUBM, SPT
- **Software - Infrastructure** 4곳: BLSH, PRGS, SABR, RPAY
- **Medical Care Facilities** 3곳: THC, AVAH, AGL
- **Oil & Gas Midstream** 3곳: FRO, INSW, DHT

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|PBF|Oil & Gas Refining & Marketing|$10.8B|$6.10 → $17.41|+185%|+12.40%p|3/0|+50%|-48%|예|
|2|TALO|Oil & Gas E&P|$2.9B|$-0.36 → $1.66|적자→흑자|+11.51%p|5/0|+24%|미산출|예|
|3|DK|Oil & Gas Refining & Marketing|$4.9B|$2.17 → $8.35|+284%|+7.65%p|4/0|+31%|-66%|예|
|4|MPC|Oil & Gas Refining & Marketing|$133.9B|$25.27 → $55.13|+118%|+6.26%p|13/0|+56%|-28%|예|
|5|RPAY|Software - Infrastructure|$348M|$0.97 → $1.16|+20%|+4.88%p|2/1|-3%|-19%|-|
|6|MU|Semiconductors|$1078.5B|$163.35 → $206.33|+26%|+4.51%p|19/1|+12%|-12%|예|
|7|CLF|Steel|$7.3B|$0.43 → $0.96|+123%|+4.13%p|1/0|+35%|-40%|예|
|8|CODI|Conglomerates|$831M|$0.28 → $0.67|+139%|+3.53%p|4/1|+6%|-56%|예|
|9|AGL|Medical Care Facilities|$1.4B|$-0.62 → $2.36|적자→흑자|+3.47%p|6/0|-29%|미산출|-|
|10|NOG|Oil & Gas E&P|$2.8B|$3.85 → $4.69|+22%|+3.20%p|2/1|+30%|+6%|예|
|11|TRLV|Drug Manufacturers - Specialty & Generic|$1.9B|$0.24 → $0.56|+132%|+3.14%p|1/0|+20%|-48%|예|
|12|SPT|Software - Application|$679M|$1.20 → $1.54|+28%|+3.05%p|9/0|+30%|+1%|-|
|13|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.03%p|1/0|-3%|-62%|예|
|14|TXO|Oil & Gas E&P|$808M|$0.88 → $1.31|+49%|+2.96%p|1/0|+12%|-25%|예|
|15|BP|Oil & Gas Integrated|$125.0B|$3.92 → $5.35|+37%|+2.95%p|8/0|+18%|-14%|예|
|16|FRO|Oil & Gas Midstream|$13.1B|$3.53 → $5.24|+48%|+2.90%p|4/1|+59%|+7%|예|
|17|DHT|Oil & Gas Midstream|$4.3B|$1.73 → $2.50|+44%|+2.89%p|2/0|+49%|+3%|-|
|18|JXN|Insurance - Life|$8.9B|$28.02 → $31.63|+13%|+2.75%p|4/0|+4%|-8%|예|
|19|INDV|Drug Manufacturers - Specialty & Generic|$4.2B|$3.92 → $4.88|+25%|+2.72%p|3/0|-13%|-30%|예|
|20|SABR|Software - Infrastructure|$730M|$0.14 → $0.19|+32%|+2.57%p|1/0|+0%|-24%|-|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$2.5B|$0.30 → $1.38|+361%|+1.40%p|1/0|-8%|-80%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.9B|$2.17 → $8.35|+284%|+7.65%p|4/0|+31%|-66%|예|
|3|SPCX|Aerospace & Defense|$2063.5B|$0.68 → $2.08|+208%|+0.90%p|3/0|+19%|-61%|예|
|4|AXTI|Semiconductor Equipment & Materials|$4.2B|$0.75 → $2.25|+199%|+2.32%p|1/0|+42%|-53%|예|
|5|PBF|Oil & Gas Refining & Marketing|$10.8B|$6.10 → $17.41|+185%|+12.40%p|3/0|+50%|-48%|예|
|6|CORT|Biotechnology|$12.7B|$1.63 → $4.40|+170%|+2.35%p|2/0|+31%|-51%|-|
|7|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.03%p|1/0|-3%|-62%|예|
|8|BLTE|Biotechnology|$6.1B|$0.94 → $2.26|+139%|+0.87%p|5/2|+1%|-58%|예|
|9|CODI|Conglomerates|$831M|$0.28 → $0.67|+139%|+3.53%p|4/1|+6%|-56%|예|
|10|CVI|Oil & Gas Refining & Marketing|$6.3B|$1.70 → $3.86|+126%|+3.41%p|2/0|+89%|-17%|예|
|11|CLF|Steel|$7.3B|$0.43 → $0.96|+123%|+4.13%p|1/0|+35%|-40%|예|
|12|CBRL|Restaurants|$1.4B|$1.16 → $2.20|+90%|+1.70%p|3/0|+20%|-37%|예|
|13|PUBM|Software - Application|$860M|$0.49 → $0.81|+67%|+1.72%p|5/0|+39%|-17%|예|
|14|FSLY|Software - Application|$4.3B|$0.39 → $0.64|+63%|+0.91%p|6/0|+33%|-18%|예|
|15|TEAM|Software - Application|$52.7B|$1.39 → $2.19|+57%|+0.38%p|1/0|+125%|+44%|예|
|16|SMTC|Semiconductors|$16.1B|$3.89 → $5.86|+51%|+1.14%p|1/0|+35%|-10%|예|
|17|TXO|Oil & Gas E&P|$808M|$0.88 → $1.31|+49%|+2.96%p|1/0|+12%|-25%|예|
|18|OSCR|Healthcare Plans|$10.4B|$1.49 → $2.22|+49%|+2.16%p|6/0|+17%|-22%|예|
|19|FRO|Oil & Gas Midstream|$13.1B|$3.53 → $5.24|+48%|+2.90%p|4/1|+59%|+7%|예|
|20|INSW|Oil & Gas Midstream|$6.2B|$6.44 → $9.56|+48%|+2.50%p|1/0|+42%|-4%|-|

전체 결과: `data/processed/revision_screen/20261014T050334Z_38514422416-1.json.gz`
