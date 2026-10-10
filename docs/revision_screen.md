# 이익 예상치 상향 스크리너

최신 시도: 2026-10-10 15:01 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-10 15:01 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7663|7662|1|0|0|
|EPS 예상치|3221|2418|803|0|0|
|업종(후보)|105|105|0|0|0|
|주가 비교(상위)|32|32|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas Refining & Marketing** 8곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR
- **Semiconductors** 6곳: NVDA, MU, INTC, LSCC, SMTC, MXL
- **Oil & Gas Integrated** 6곳: CVX, SHEL, TTE, BP, EQNR, E
- **Semiconductor Equipment & Materials** 6곳: FORM, ACMR, KLIC, AXTI, UCTT, AEHR
- **Oil & Gas E&P** 6곳: CHRD, MTDR, TALO, NOG, KOS, TXO
- **Banks - Regional** 6곳: HBT, AMTB, HTB, VBNK, PEBO, BSVN
- **Software - Application** 5곳: TEAM, FSLY, MNDY, PUBM, SPT
- **Computer Hardware** 4곳: SNDK, STX, WDC, P
- **Oil & Gas Midstream** 4곳: FRO, KNTK, INSW, DHT
- **Software - Infrastructure** 4곳: BLSH, PRGS, SABR, RPAY
- **Electronic Components** 3곳: CLS, JBL, TTMI
- **Medical Care Facilities** 3곳: THC, AVAH, AGL
- **Credit Services** 3곳: BFH, AGM, ECPG

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|PBF|Oil & Gas Refining & Marketing|$10.0B|$6.10 → $17.41|+185%|+13.41%p|4/0|+58%|-44%|예|
|2|TALO|Oil & Gas E&P|$2.8B|$-0.36 → $1.66|적자→흑자|+12.03%p|5/0|+24%|미산출|예|
|3|DK|Oil & Gas Refining & Marketing|$4.6B|$1.94 → $7.79|+302%|+7.85%p|6/0|+34%|-67%|-|
|4|MPC|Oil & Gas Refining & Marketing|$127.8B|$23.60 → $51.77|+119%|+6.19%p|12/0|+60%|-27%|예|
|5|RPAY|Software - Infrastructure|$341M|$0.97 → $1.16|+20%|+4.98%p|2/1|-5%|-21%|-|
|6|JXN|Insurance - Life|$8.8B|$26.52 → $32.08|+21%|+4.28%p|4/0|+11%|-8%|예|
|7|MU|Semiconductors|$1162.1B|$163.35 → $206.33|+26%|+4.18%p|4/1|+5%|-17%|예|
|8|CLF|Steel|$7.4B|$0.43 → $0.93|+114%|+3.81%p|1/0|+38%|-36%|예|
|9|AGL|Medical Care Facilities|$1.4B|$-0.62 → $2.36|적자→흑자|+3.62%p|6/0|-28%|미산출|-|
|10|UCTT|Semiconductor Equipment & Materials|$3.1B|$3.94 → $6.24|+59%|+3.36%p|4/0|-36%|-59%|예|
|11|SPT|Software - Application|$667M|$1.20 → $1.54|+28%|+3.10%p|9/0|+33%|+3%|-|
|12|DHT|Oil & Gas Midstream|$4.0B|$1.74 → $2.50|+44%|+3.09%p|2/0|+39%|-3%|예|
|13|FRO|Oil & Gas Midstream|$12.5B|$3.53 → $5.24|+48%|+3.05%p|4/1|+47%|-1%|예|
|14|TXO|Oil & Gas E&P|$792M|$0.88 → $1.31|+49%|+3.02%p|1/0|+9%|-27%|예|
|15|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.02%p|1/0|-2%|-62%|예|
|16|TRLV|Drug Manufacturers - Specialty & Generic|$2.1B|$0.24 → $0.56|+132%|+2.97%p|1/0|+24%|-47%|예|
|17|BP|Oil & Gas Integrated|$119.1B|$4.07 → $5.33|+31%|+2.73%p|6/1|+18%|-10%|예|
|18|DAN|Auto Parts|$3.2B|$3.37 → $4.17|+24%|+2.72%p|2/1|+7%|-13%|-|
|19|INDV|Drug Manufacturers - Specialty & Generic|$4.2B|$3.92 → $4.88|+25%|+2.69%p|3/0|-12%|-29%|예|
|20|INSW|Oil & Gas Midstream|$5.9B|$6.44 → $9.56|+48%|+2.61%p|1/0|+35%|-9%|-|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$2.8B|$0.30 → $1.38|+361%|+1.28%p|1/0|+17%|-75%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.6B|$1.94 → $7.79|+302%|+7.85%p|6/0|+34%|-67%|-|
|3|SPCX|Aerospace & Defense|$2143.0B|$0.68 → $2.04|+201%|+0.84%p|3/0|+12%|-63%|예|
|4|AXTI|Semiconductor Equipment & Materials|$4.5B|$0.75 → $2.25|+199%|+2.19%p|1/0|+20%|-60%|예|
|5|PBF|Oil & Gas Refining & Marketing|$10.0B|$6.10 → $17.41|+185%|+13.41%p|4/0|+58%|-44%|예|
|6|CORT|Biotechnology|$13.1B|$1.63 → $4.40|+170%|+2.29%p|2/0|+32%|-51%|-|
|7|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.02%p|1/0|-2%|-62%|예|
|8|BLTE|Biotechnology|$6.2B|$0.94 → $2.26|+139%|+0.85%p|5/2|+4%|-57%|예|
|9|CVI|Oil & Gas Refining & Marketing|$5.8B|$1.70 → $3.86|+126%|+3.71%p|2/0|+87%|-17%|예|
|10|CLF|Steel|$7.4B|$0.43 → $0.93|+114%|+3.81%p|1/0|+38%|-36%|예|
|11|CBRL|Restaurants|$1.3B|$1.16 → $2.12|+83%|+1.68%p|3/0|+14%|-38%|예|
|12|PUBM|Software - Application|$849M|$0.49 → $0.81|+67%|+1.74%p|5/0|+38%|-17%|예|
|13|FSLY|Software - Application|$4.7B|$0.39 → $0.64|+63%|+0.84%p|6/0|+50%|-8%|예|
|14|UCTT|Semiconductor Equipment & Materials|$3.1B|$3.94 → $6.24|+59%|+3.36%p|4/0|-36%|-59%|예|
|15|TEAM|Software - Application|$52.3B|$1.39 → $2.19|+57%|+0.38%p|1/0|+133%|+48%|예|
|16|SMTC|Semiconductors|$17.5B|$3.89 → $5.86|+51%|+1.05%p|13/0|+38%|-9%|예|
|17|TXO|Oil & Gas E&P|$792M|$0.88 → $1.31|+49%|+3.02%p|1/0|+9%|-27%|예|
|18|FRO|Oil & Gas Midstream|$12.5B|$3.53 → $5.24|+48%|+3.05%p|4/1|+47%|-1%|예|
|19|INSW|Oil & Gas Midstream|$5.9B|$6.44 → $9.56|+48%|+2.61%p|1/0|+35%|-9%|-|
|20|OSCR|Healthcare Plans|$10.3B|$1.48 → $2.17|+46%|+2.04%p|6/0|+9%|-25%|예|

전체 결과: `data/processed/revision_screen/20261010T060144Z_38029430169-1.json.gz`
