# 이익 예상치 상향 스크리너

최신 시도: 2026-11-06 16:00 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-11-06 16:00 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7626|7626|0|0|0|
|EPS 예상치|3168|2392|776|0|0|
|업종(후보)|107|107|0|0|0|
|주가 비교(상위)|28|28|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 17곳: COP, EOG, OXY, FANG, PR, OVV, APA, AR, SM, CHRD, MTDR, MUR, CRGY, NOG, REPX, TXO, GRNT
- **Semiconductors** 9곳: NVDA, MU, MPWR, CBRS, SWKS, LSCC, SMTC, SIMO, MXL
- **Oil & Gas Integrated** 9곳: CVX, SHEL, TTE, BP, EQNR, E, EC, DEC, PBR-A
- **Oil & Gas Refining & Marketing** 9곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR, DKL
- **Software - Application** 6곳: TEAM, U, CHYM, MNDY, FSLY, SPT
- **Oil & Gas Midstream** 6곳: VG, FRO, INSW, STNG, DHT, TNK
- **Computer Hardware** 5곳: DELL, SNDK, STX, WDC, SMCI
- **Communication Equipment** 4곳: HPE, LITE, CIEN, HLIT
- **Steel** 3곳: NUE, STLD, CLF
- **Electronics & Computer Distribution** 3곳: SNX, ARW, SCSC
- **Banks - Regional** 3곳: HBT, BSVN, SUPV

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$884M|$2.42 → $7.40|+206%|+38.92%p|2/0|-8%|-70%|-|
|2|PBF|Oil & Gas Refining & Marketing|$8.1B|$8.97 → $18.56|+107%|+14.03%p|3/1|+11%|-46%|예|
|3|CLF|Steel|$6.4B|$0.59 → $1.71|+189%|+9.89%p|3/0|-8%|-68%|예|
|4|DK|Oil & Gas Refining & Marketing|$3.8B|$3.21 → $9.32|+190%|+9.78%p|7/1|+7%|-63%|예|
|5|DINO|Oil & Gas Refining & Marketing|$16.8B|$9.00 → $17.90|+99%|+9.10%p|12/0|+20%|-40%|예|
|6|TXO|Oil & Gas E&P|$703M|$0.97 → $1.96|+102%|+7.83%p|3/0|-8%|-54%|예|
|7|GRNT|Oil & Gas E&P|$616M|$0.64 → $1.00|+57%|+7.78%p|3/0|-4%|-39%|-|
|8|SMCI|Computer Hardware|$17.8B|$3.86 → $5.82|+51%|+7.25%p|4/0|-13%|-42%|예|
|9|DHT|Oil & Gas Midstream|$3.3B|$1.81 → $3.24|+79%|+7.00%p|2/0|+9%|-39%|예|
|10|CRGY|Oil & Gas E&P|$4.4B|$2.27 → $3.00|+32%|+6.61%p|9/0|-4%|-27%|-|
|11|TNK|Oil & Gas Midstream|$2.8B|$9.12 → $14.45|+58%|+6.50%p|2/0|+6%|-33%|-|
|12|MU|Semiconductors|$742.7B|$166.89 → $207.76|+24%|+6.23%p|20/1|-25%|-40%|예|
|13|PBR-A|Oil & Gas Integrated|$114.5B|$3.52 → $4.56|+29%|+6.18%p|3/0|+4%|-20%|예|
|14|FRO|Oil & Gas Midstream|$10.0B|$3.72 → $6.24|+68%|+5.65%p|4/1|+12%|-33%|예|
|15|TTMI|Electronic Components|$6.6B|$5.40 → $8.34|+54%|+4.72%p|4/0|-55%|-71%|예|
|16|VSNT|Entertainment|$4.6B|$6.69 → $8.25|+23%|+4.58%p|1/0|-12%|-29%|-|
|17|TBLA|Internet Content & Information|$578M|$0.23 → $0.33|+41%|+4.36%p|3/1|-47%|-62%|예|
|18|WDC|Computer Hardware|$100.2B|$29.34 → $40.40|+38%|+4.13%p|18/0|-38%|-55%|예|
|19|SNDK|Computer Hardware|$114.7B|$255.63 → $287.26|+12%|+3.92%p|1/0|-34%|-41%|-|
|20|MXL|Semiconductors|$4.0B|$2.58 → $4.30|+66%|+3.87%p|10/0|-41%|-64%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|SPCX|Aerospace & Defense|$1678.9B|$0.57 → $4.03|+608%|+2.80%p|13/0|-7%|-87%|예|
|2|DEC|Oil & Gas Integrated|$884M|$2.42 → $7.40|+206%|+38.92%p|2/0|-8%|-70%|-|
|3|DK|Oil & Gas Refining & Marketing|$3.8B|$3.21 → $9.32|+190%|+9.78%p|7/1|+7%|-63%|예|
|4|CLF|Steel|$6.4B|$0.59 → $1.71|+189%|+9.89%p|3/0|-8%|-68%|예|
|5|GKOS|Medical Devices|$13.0B|$0.50 → $1.40|+179%|+0.41%p|3/0|+22%|-56%|예|
|6|CODI|Conglomerates|$863M|$0.28 → $0.67|+139%|+3.40%p|4/1|+4%|-56%|예|
|7|CVI|Oil & Gas Refining & Marketing|$4.0B|$1.91 → $4.55|+138%|+6.62%p|4/0|+28%|-46%|예|
|8|PBF|Oil & Gas Refining & Marketing|$8.1B|$8.97 → $18.56|+107%|+14.03%p|3/1|+11%|-46%|예|
|9|TXO|Oil & Gas E&P|$703M|$0.97 → $1.96|+102%|+7.83%p|3/0|-8%|-54%|예|
|10|DHT|Oil & Gas Midstream|$3.3B|$1.81 → $3.24|+79%|+7.00%p|2/0|+9%|-39%|예|
|11|TEAM|Software - Application|$46.4B|$1.22 → $2.19|+79%|+0.53%p|2/0|+23%|-31%|예|
|12|SMTC|Semiconductors|$8.5B|$3.92 → $6.67|+70%|+3.01%p|14/0|-34%|-61%|예|
|13|FRO|Oil & Gas Midstream|$10.0B|$3.72 → $6.24|+68%|+5.65%p|4/1|+12%|-33%|예|
|14|MXL|Semiconductors|$4.0B|$2.58 → $4.30|+66%|+3.87%p|10/0|-41%|-64%|예|
|15|FSLY|Software - Application|$2.5B|$0.40 → $0.64|+62%|+1.60%p|7/0|-33%|-59%|예|
|16|TNK|Oil & Gas Midstream|$2.8B|$9.12 → $14.45|+58%|+6.50%p|2/0|+6%|-33%|-|
|17|GRNT|Oil & Gas E&P|$616M|$0.64 → $1.00|+57%|+7.78%p|3/0|-4%|-39%|-|
|18|TTMI|Electronic Components|$6.6B|$5.40 → $8.34|+54%|+4.72%p|4/0|-55%|-71%|예|
|19|SMCI|Computer Hardware|$17.8B|$3.86 → $5.82|+51%|+7.25%p|4/0|-13%|-42%|예|
|20|VSEC|Aerospace & Defense|$4.6B|$5.68 → $8.26|+46%|+1.57%p|4/2|-24%|-48%|예|

전체 결과: `data/processed/revision_screen/20261106T070026Z_42177705259-1.json.gz`
