# 이익 예상치 상향 스크리너

최신 시도: 2026-10-13 15:52 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-13 15:52 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7663|7660|3|0|0|
|EPS 예상치|3263|2429|834|0|0|
|업종(후보)|104|104|0|0|0|
|주가 비교(상위)|33|33|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas Refining & Marketing** 8곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR
- **Oil & Gas E&P** 8곳: APA, SM, CHRD, MTDR, TALO, NOG, KOS, TXO
- **Semiconductors** 6곳: NVDA, MU, INTC, LSCC, SMTC, MXL
- **Oil & Gas Integrated** 6곳: CVX, SHEL, TTE, BP, EQNR, E
- **Semiconductor Equipment & Materials** 6곳: FORM, ACMR, KLIC, AXTI, AEHR, ICHR
- **Banks - Regional** 6곳: HBT, AMTB, HTB, VBNK, PEBO, BSVN
- **Software - Application** 5곳: TEAM, FSLY, MNDY, PUBM, SPT
- **Computer Hardware** 4곳: SNDK, STX, WDC, P
- **Software - Infrastructure** 4곳: BLSH, PRGS, SABR, RPAY
- **Medical Care Facilities** 3곳: THC, AVAH, AGL
- **Oil & Gas Midstream** 3곳: FRO, INSW, DHT

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|PBF|Oil & Gas Refining & Marketing|$10.1B|$6.10 → $17.41|+185%|+13.30%p|3/0|+45%|-49%|예|
|2|TALO|Oil & Gas E&P|$2.9B|$-0.36 → $1.66|적자→흑자|+11.65%p|5/0|+24%|미산출|예|
|3|DK|Oil & Gas Refining & Marketing|$4.7B|$2.17 → $8.35|+284%|+7.99%p|6/0|+30%|-66%|예|
|4|MPC|Oil & Gas Refining & Marketing|$133.9B|$25.27 → $52.16|+106%|+5.86%p|13/0|+53%|-26%|예|
|5|RPAY|Software - Infrastructure|$337M|$0.97 → $1.16|+20%|+5.05%p|2/1|-7%|-22%|-|
|6|MU|Semiconductors|$1119.0B|$163.35 → $206.33|+26%|+4.35%p|19/1|+9%|-13%|예|
|7|CLF|Steel|$7.4B|$0.43 → $0.96|+123%|+4.12%p|1/0|+31%|-41%|예|
|8|JXN|Insurance - Life|$8.9B|$27.14 → $31.96|+18%|+3.67%p|4/0|+6%|-10%|예|
|9|AGL|Medical Care Facilities|$1.4B|$-0.62 → $2.36|적자→흑자|+3.49%p|6/0|-31%|미산출|-|
|10|SPT|Software - Application|$669M|$1.20 → $1.54|+28%|+3.09%p|9/0|+26%|-2%|-|
|11|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.07%p|1/0|-4%|-62%|예|
|12|BP|Oil & Gas Integrated|$120.4B|$3.92 → $5.34|+36%|+3.05%p|8/0|+13%|-17%|예|
|13|TRLV|Drug Manufacturers - Specialty & Generic|$2.0B|$0.24 → $0.56|+132%|+3.05%p|1/0|+20%|-48%|예|
|14|TXO|Oil & Gas E&P|$796M|$0.88 → $1.31|+49%|+3.01%p|1/0|+10%|-27%|예|
|15|DHT|Oil & Gas Midstream|$4.2B|$1.73 → $2.50|+44%|+2.93%p|2/0|+46%|+1%|-|
|16|FRO|Oil & Gas Midstream|$13.2B|$3.53 → $5.24|+48%|+2.89%p|4/1|+56%|+5%|예|
|17|NOG|Oil & Gas E&P|$2.7B|$3.89 → $4.58|+18%|+2.75%p|2/1|+25%|+6%|예|
|18|INDV|Drug Manufacturers - Specialty & Generic|$4.3B|$3.92 → $4.88|+25%|+2.67%p|3/0|-12%|-29%|예|
|19|INSW|Oil & Gas Midstream|$6.2B|$6.44 → $9.56|+48%|+2.51%p|1/0|+40%|-6%|-|
|20|SABR|Software - Infrastructure|$759M|$0.14 → $0.19|+32%|+2.48%p|1/0|+7%|-19%|-|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$2.6B|$0.30 → $1.38|+361%|+1.39%p|1/0|-11%|-81%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.7B|$2.17 → $8.35|+284%|+7.99%p|6/0|+30%|-66%|예|
|3|SPCX|Aerospace & Defense|$2152.9B|$0.68 → $2.08|+208%|+0.86%p|3/0|+21%|-61%|예|
|4|AXTI|Semiconductor Equipment & Materials|$4.1B|$0.75 → $2.25|+199%|+2.42%p|1/0|+16%|-61%|예|
|5|PBF|Oil & Gas Refining & Marketing|$10.1B|$6.10 → $17.41|+185%|+13.30%p|3/0|+45%|-49%|예|
|6|CORT|Biotechnology|$13.1B|$1.63 → $4.40|+170%|+2.29%p|2/0|+35%|-50%|-|
|7|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.07%p|1/0|-4%|-62%|예|
|8|BLTE|Biotechnology|$6.4B|$0.94 → $2.26|+139%|+0.83%p|5/2|+6%|-56%|예|
|9|CVI|Oil & Gas Refining & Marketing|$5.9B|$1.70 → $3.86|+126%|+3.65%p|2/0|+81%|-20%|예|
|10|CLF|Steel|$7.4B|$0.43 → $0.96|+123%|+4.12%p|1/0|+31%|-41%|예|
|11|CBRL|Restaurants|$1.3B|$1.16 → $2.20|+90%|+1.77%p|3/0|+14%|-40%|예|
|12|PUBM|Software - Application|$844M|$0.49 → $0.81|+67%|+1.75%p|5/0|+34%|-19%|예|
|13|FSLY|Software - Application|$4.2B|$0.39 → $0.64|+63%|+0.94%p|6/0|+32%|-19%|예|
|14|TEAM|Software - Application|$52.6B|$1.39 → $2.19|+57%|+0.38%p|1/0|+126%|+44%|예|
|15|SMTC|Semiconductors|$15.7B|$3.89 → $5.86|+51%|+1.17%p|1/0|+24%|-17%|예|
|16|TXO|Oil & Gas E&P|$796M|$0.88 → $1.31|+49%|+3.01%p|1/0|+10%|-27%|예|
|17|OSCR|Healthcare Plans|$10.5B|$1.49 → $2.22|+49%|+2.15%p|6/0|+11%|-26%|예|
|18|FRO|Oil & Gas Midstream|$13.2B|$3.53 → $5.24|+48%|+2.89%p|4/1|+56%|+5%|예|
|19|INSW|Oil & Gas Midstream|$6.2B|$6.44 → $9.56|+48%|+2.51%p|1/0|+40%|-6%|-|
|20|VSEC|Aerospace & Defense|$4.7B|$5.68 → $8.28|+46%|+1.55%p|9/1|-18%|-44%|-|

전체 결과: `data/processed/revision_screen/20261013T065241Z_38359168209-1.json.gz`
