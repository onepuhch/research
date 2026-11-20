# 이익 예상치 상향 스크리너

최신 시도: 2026-11-20 16:28 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-11-20 16:28 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7609|7609|0|0|0|
|EPS 예상치|3121|2383|738|0|0|
|업종(후보)|122|122|0|0|0|
|주가 비교(상위)|29|29|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 15곳: COP, EOG, OXY, FANG, PR, OVV, APA, CHRD, SM, MTDR, CRGY, TALO, REPX, GRNT, TXO
- **Semiconductors** 10곳: NVDA, SKHY, MU, MPWR, CBRS, SWKS, LSCC, SIMO, MXL, LASR
- **Oil & Gas Integrated** 8곳: XOM, CVX, SHEL, TTE, BP, EQNR, E, CVE
- **Oil & Gas Midstream** 8곳: LNG, VG, CQP, FRO, INSW, CMBT, STNG, DHT
- **Oil & Gas Refining & Marketing** 7곳: MPC, VLO, PSX, DINO, CVI, DK, PARR
- **Computer Hardware** 5곳: DELL, STX, WDC, P, SMCI
- **Communication Equipment** 5곳: HPE, LITE, CIEN, VIAV, HLIT
- **Software - Application** 4곳: MSTR, U, SMWB, SPT
- **Steel** 3곳: NUE, STLD, CLF
- **Electronics & Computer Distribution** 3곳: SNX, ARW, NSIT
- **Oil & Gas Drilling** 3곳: PTEN, HP, NBR
- **Software - Infrastructure** 3곳: PRGS, PGY, TLS
- **Banks - Regional** 3곳: HBT, BSVN, BWFG

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|CVI|Oil & Gas Refining & Marketing|$3.8B|$2.19 → $8.78|+301%|+19.46%p|5/0|-14%|-79%|예|
|2|MSTR|Software - Application|$36.5B|$5.21 → $21.35|+310%|+18.73%p|3/2|-28%|-82%|-|
|3|DK|Oil & Gas Refining & Marketing|$3.7B|$4.08 → $12.20|+199%|+13.47%p|7/1|-16%|-72%|예|
|4|REPX|Oil & Gas E&P|$909M|$7.89 → $11.94|+51%|+9.84%p|4/0|+8%|-29%|예|
|5|CRGY|Oil & Gas E&P|$5.2B|$2.15 → $3.17|+48%|+9.49%p|12/0|-24%|-48%|-|
|6|CLF|Steel|$6.7B|$0.63 → $1.70|+171%|+9.15%p|5/0|+4%|-62%|-|
|7|DINO|Oil & Gas Refining & Marketing|$15.2B|$9.37 → $17.52|+87%|+9.08%p|12/1|-8%|-51%|-|
|8|SKHY|Semiconductors|$840.6B|$32.24 → $41.35|+28%|+7.64%p|3/0|-27%|-43%|-|
|9|TXO|Oil & Gas E&P|$700M|$0.97 → $1.92|+98%|+7.55%p|3/0|-11%|-55%|-|
|10|AMC|Entertainment|$2.5B|$-0.12 → $0.08|적자→흑자|+7.47%p|2/0|+9%|미산출|-|
|11|DHT|Oil & Gas Midstream|$3.5B|$1.87 → $3.34|+79%|+6.86%p|3/0|+8%|-39%|예|
|12|SMCI|Computer Hardware|$15.7B|$5.33 → $6.95|+30%|+6.79%p|12/0|-36%|-51%|예|
|13|GPRE|Chemicals|$823M|$1.56 → $2.35|+50%|+6.73%p|2/1|-28%|-52%|-|
|14|CLMT|Specialty Chemicals|$2.7B|$1.59 → $3.42|+115%|+5.88%p|2/1|-37%|-70%|-|
|15|VG|Oil & Gas Midstream|$30.5B|$0.97 → $1.67|+72%|+5.80%p|3/1|-15%|-50%|예|
|16|SATL|Aerospace & Defense|$422M|$-0.03 → $0.12|적자→흑자|+5.62%p|3/0|-52%|미산출|예|
|17|MU|Semiconductors|$781.2B|$169.12 → $207.76|+23%|+5.60%p|3/1|-29%|-42%|예|
|18|FRO|Oil & Gas Midstream|$10.0B|$3.95 → $6.24|+58%|+5.12%p|4/1|+2%|-35%|예|
|19|NMM|Marine Shipping|$2.4B|$17.33 → $21.48|+24%|+5.04%p|1/0|-7%|-25%|예|
|20|BUR|Asset Management|$753M|$0.54 → $0.69|+28%|+4.41%p|1/0|-20%|-38%|-|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|MSTR|Software - Application|$36.5B|$5.21 → $21.35|+310%|+18.73%p|3/2|-28%|-82%|-|
|2|CVI|Oil & Gas Refining & Marketing|$3.8B|$2.19 → $8.78|+301%|+19.46%p|5/0|-14%|-79%|예|
|3|DK|Oil & Gas Refining & Marketing|$3.7B|$4.08 → $12.20|+199%|+13.47%p|7/1|-16%|-72%|예|
|4|GKOS|Medical Devices|$14.1B|$0.50 → $1.40|+178%|+0.38%p|10/0|+29%|-54%|예|
|5|CLF|Steel|$6.7B|$0.63 → $1.70|+171%|+9.15%p|5/0|+4%|-62%|-|
|6|SPCX|Aerospace & Defense|$1880.0B|$1.78 → $4.17|+134%|+1.72%p|14/1|+1%|-57%|예|
|7|BXDC|REIT - Specialty|$1.6B|$0.49 → $1.11|+126%|+3.78%p|2/0|-20%|-65%|-|
|8|CLMT|Specialty Chemicals|$2.7B|$1.59 → $3.42|+115%|+5.88%p|2/1|-37%|-70%|-|
|9|TXO|Oil & Gas E&P|$700M|$0.97 → $1.92|+98%|+7.55%p|3/0|-11%|-55%|-|
|10|DINO|Oil & Gas Refining & Marketing|$15.2B|$9.37 → $17.52|+87%|+9.08%p|12/1|-8%|-51%|-|
|11|DHT|Oil & Gas Midstream|$3.5B|$1.87 → $3.34|+79%|+6.86%p|3/0|+8%|-39%|예|
|12|VG|Oil & Gas Midstream|$30.5B|$0.97 → $1.67|+72%|+5.80%p|3/1|-15%|-50%|예|
|13|MXL|Semiconductors|$4.4B|$2.58 → $4.30|+66%|+3.57%p|10/0|-28%|-57%|예|
|14|CODI|Conglomerates|$919M|$0.55 → $0.90|+62%|+2.83%p|4/1|+4%|-36%|-|
|15|FRO|Oil & Gas Midstream|$10.0B|$3.95 → $6.24|+58%|+5.12%p|4/1|+2%|-35%|예|
|16|CHRD|Oil & Gas E&P|$7.2B|$13.86 → $21.41|+54%|+5.55%p|15/1|-8%|-40%|예|
|17|TTMI|Electronic Components|$7.2B|$5.40 → $8.34|+54%|+4.32%p|4/0|-38%|-60%|예|
|18|U|Software - Application|$20.7B|$1.72 → $2.65|+54%|+1.99%p|9/0|-0%|-35%|예|
|19|PTEN|Oil & Gas Drilling|$3.7B|$0.31 → $0.48|+52%|+1.69%p|6/0|-21%|-48%|-|
|20|REPX|Oil & Gas E&P|$909M|$7.89 → $11.94|+51%|+9.84%p|4/0|+8%|-29%|예|

전체 결과: `data/processed/revision_screen/20261120T072851Z_44694982448-1.json.gz`
