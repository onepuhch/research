# 이익 예상치 상향 스크리너

최신 시도: 2026-10-20 14:00 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-10-20 14:00 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7645|7645|0|0|0|
|EPS 예상치|3224|2414|810|0|0|
|업종(후보)|101|101|0|0|0|
|주가 비교(상위)|32|32|0|0|0|

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
- **Semiconductors** 6곳: NVDA, MU, INTC, ALAB, LSCC, SMTC
- **Computer Hardware** 5곳: DELL, SNDK, STX, WDC, P
- **Semiconductor Equipment & Materials** 5곳: KLIC, ACMR, AXTI, AEHR, ICHR
- **Software - Application** 4곳: TEAM, MNDY, FSLY, PUBM
- **Banks - Regional** 4곳: PEBO, HBT, AMTB, BSVN

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$1.0B|$2.69 → $7.40|+175%|+32.33%p|2/0|+9%|-60%|예|
|2|PBF|Oil & Gas Refining & Marketing|$9.6B|$7.41 → $17.38|+135%|+12.27%p|3/1|+26%|-46%|-|
|3|DK|Oil & Gas Refining & Marketing|$4.6B|$2.86 → $8.41|+194%|+7.38%p|4/0|+14%|-61%|예|
|4|TXO|Oil & Gas E&P|$785M|$0.88 → $1.92|+119%|+7.38%p|1/0|+8%|-51%|예|
|5|MPC|Oil & Gas Refining & Marketing|$138.3B|$26.91 → $56.70|+111%|+6.29%p|12/2|+50%|-29%|예|
|6|MU|Semiconductors|$1023.8B|$163.35 → $206.89|+27%|+4.81%p|19/1|-6%|-26%|예|
|7|CRGY|Oil & Gas E&P|$4.5B|$2.29 → $2.86|+25%|+4.17%p|7/0|+20%|-4%|-|
|8|CLF|Steel|$8.0B|$0.38 → $0.95|+152%|+4.06%p|1/0|+49%|-41%|예|
|9|CODI|Conglomerates|$756M|$0.28 → $0.67|+139%|+3.88%p|4/1|-3%|-59%|예|
|10|ECHO|Telecom Services|$25.1B|$10.38 → $13.43|+29%|+3.54%p|1/0|-7%|-28%|-|
|11|FRO|Oil & Gas Midstream|$11.3B|$3.53 → $5.24|+48%|+3.38%p|4/1|+34%|-10%|예|
|12|DHT|Oil & Gas Midstream|$3.7B|$1.73 → $2.50|+44%|+3.34%p|2/0|+27%|-12%|예|
|13|GRNT|Oil & Gas E&P|$748M|$0.64 → $0.83|+29%|+3.31%p|1/0|+17%|-10%|-|
|14|TRLV|Drug Manufacturers - Specialty & Generic|$2.0B|$0.24 → $0.56|+132%|+3.08%p|1/0|+19%|-49%|예|
|15|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.04%p|1/0|-6%|-63%|예|
|16|PBR-A|Oil & Gas Integrated|$157.2B|$3.41 → $4.07|+20%|+2.89%p|2/1|+37%|+15%|예|
|17|INDV|Drug Manufacturers - Specialty & Generic|$4.0B|$3.92 → $4.88|+25%|+2.84%p|3/0|-16%|-33%|예|
|18|JXN|Insurance - Life|$8.7B|$28.02 → $31.63|+13%|+2.80%p|1/0|+4%|-8%|예|
|19|BP|Oil & Gas Integrated|$127.3B|$4.12 → $5.49|+33%|+2.78%p|8/0|+14%|-14%|예|
|20|BLSH|Software - Infrastructure|$4.2B|$2.53 → $3.27|+29%|+2.70%p|1/0|+16%|-10%|-|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$2.1B|$0.30 → $1.38|+361%|+1.71%p|1/0|-32%|-85%|예|
|2|SPCX|Aerospace & Defense|$1949.3B|$0.65 → $2.13|+227%|+1.00%p|4/0|+28%|-61%|예|
|3|AXTI|Semiconductor Equipment & Materials|$3.7B|$0.75 → $2.25|+199%|+2.64%p|1/0|+7%|-64%|예|
|4|DK|Oil & Gas Refining & Marketing|$4.6B|$2.86 → $8.41|+194%|+7.38%p|4/0|+14%|-61%|예|
|5|DEC|Oil & Gas Integrated|$1.0B|$2.69 → $7.40|+175%|+32.33%p|2/0|+9%|-60%|예|
|6|NBR|Oil & Gas Drilling|$1.2B|$1.57 → $4.00|+155%|+3.04%p|1/0|-6%|-63%|예|
|7|CLF|Steel|$8.0B|$0.38 → $0.95|+152%|+4.06%p|1/0|+49%|-41%|예|
|8|CVI|Oil & Gas Refining & Marketing|$6.0B|$1.74 → $4.24|+144%|+4.18%p|4/0|+72%|-30%|예|
|9|CODI|Conglomerates|$756M|$0.28 → $0.67|+139%|+3.88%p|4/1|-3%|-59%|예|
|10|PBF|Oil & Gas Refining & Marketing|$9.6B|$7.41 → $17.38|+135%|+12.27%p|3/1|+26%|-46%|-|
|11|TXO|Oil & Gas E&P|$785M|$0.88 → $1.92|+119%|+7.38%p|1/0|+8%|-51%|예|
|12|CBRL|Restaurants|$1.5B|$1.16 → $2.20|+90%|+1.51%p|3/0|+30%|-32%|예|
|13|SMTC|Semiconductors|$13.3B|$3.90 → $6.67|+71%|+1.95%p|1/0|+4%|-39%|예|
|14|PUBM|Software - Application|$775M|$0.49 → $0.81|+67%|+1.91%p|5/0|+34%|-19%|예|
|15|FSLY|Software - Application|$3.7B|$0.40 → $0.64|+62%|+1.07%p|7/0|+12%|-31%|예|
|16|TEAM|Software - Application|$54.4B|$1.37 → $2.19|+60%|+0.38%p|1/0|+152%|+57%|예|
|17|OSCR|Healthcare Plans|$10.0B|$1.49 → $2.22|+49%|+2.25%p|6/0|+10%|-26%|예|
|18|FRO|Oil & Gas Midstream|$11.3B|$3.53 → $5.24|+48%|+3.38%p|4/1|+34%|-10%|예|
|19|VSEC|Aerospace & Defense|$4.4B|$5.68 → $8.28|+46%|+1.65%p|2/1|-20%|-45%|예|
|20|TTMI|Electronic Components|$10.4B|$5.40 → $7.86|+46%|+2.48%p|4/0|-32%|-53%|예|

전체 결과: `data/processed/revision_screen/20261020T050038Z_39372419498-1.json.gz`
