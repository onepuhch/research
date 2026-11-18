# 이익 예상치 상향 스크리너

최신 시도: 2026-11-18 16:42 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-11-18 16:42 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7608|7608|0|0|0|
|EPS 예상치|3139|2392|747|0|0|
|업종(후보)|117|117|0|0|0|
|주가 비교(상위)|27|27|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 16곳: COP, EOG, OXY, FANG, PR, OVV, APA, CHRD, SM, MTDR, CRGY, MUR, TALO, REPX, GRNT, TXO
- **Semiconductors** 9곳: SKHY, MU, MPWR, CBRS, SWKS, LSCC, SIMO, MXL, LASR
- **Oil & Gas Integrated** 8곳: XOM, CVX, SHEL, TTE, BP, EQNR, E, CVE
- **Oil & Gas Midstream** 8곳: LNG, VG, CQP, FRO, INSW, CMBT, STNG, DHT
- **Oil & Gas Refining & Marketing** 7곳: MPC, VLO, PSX, DINO, CVI, DK, PARR
- **Computer Hardware** 6곳: DELL, SNDK, STX, WDC, P, SMCI
- **Communication Equipment** 5곳: HPE, LITE, CIEN, VIAV, HLIT
- **Software - Application** 4곳: MSTR, U, CHYM, SPT
- **Steel** 3곳: NUE, STLD, CLF
- **Electronics & Computer Distribution** 3곳: SNX, ARW, NSIT
- **Software - Infrastructure** 3곳: PRGS, PGY, TLS
- **Banks - Regional** 3곳: HBT, BSVN, BWFG

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|CVI|Oil & Gas Refining & Marketing|$4.2B|$2.19 → $8.78|+301%|+17.35%p|5/0|+6%|-74%|예|
|2|MSTR|Software - Application|$40.8B|$5.21 → $21.35|+310%|+16.72%p|3/2|-14%|-79%|-|
|3|DK|Oil & Gas Refining & Marketing|$4.0B|$4.08 → $12.20|+199%|+12.30%p|7/1|+3%|-66%|예|
|4|REPX|Oil & Gas E&P|$946M|$7.89 → $11.94|+51%|+9.46%p|4/0|+13%|-26%|예|
|5|CLF|Steel|$6.7B|$0.63 → $1.74|+177%|+9.43%p|5/0|+10%|-60%|예|
|6|CRGY|Oil & Gas E&P|$5.5B|$2.15 → $3.16|+48%|+8.97%p|12/0|-18%|-44%|-|
|7|DINO|Oil & Gas Refining & Marketing|$16.5B|$9.37 → $17.52|+87%|+8.34%p|12/1|+5%|-44%|-|
|8|TXO|Oil & Gas E&P|$705M|$0.97 → $1.92|+98%|+7.49%p|3/0|-10%|-54%|-|
|9|SKHY|Semiconductors|$864.6B|$32.24 → $41.35|+28%|+7.43%p|3/0|-25%|-41%|-|
|10|DHT|Oil & Gas Midstream|$3.5B|$1.87 → $3.34|+79%|+6.88%p|3/0|+8%|-40%|예|
|11|SMCI|Computer Hardware|$15.9B|$5.33 → $6.95|+30%|+6.71%p|12/0|-34%|-49%|예|
|12|AMC|Entertainment|$2.8B|$-0.12 → $0.08|적자→흑자|+6.55%p|2/0|+29%|미산출|-|
|13|GPRE|Chemicals|$887M|$1.56 → $2.35|+50%|+6.25%p|2/1|-22%|-48%|-|
|14|VG|Oil & Gas Midstream|$31.5B|$0.96 → $1.66|+72%|+5.59%p|3/1|-12%|-49%|예|
|15|CLMT|Specialty Chemicals|$2.8B|$1.40 → $3.17|+127%|+5.58%p|2/1|-34%|-71%|-|
|16|FRO|Oil & Gas Midstream|$10.1B|$3.72 → $6.24|+68%|+5.57%p|4/1|+4%|-38%|예|
|17|MU|Semiconductors|$806.0B|$169.12 → $207.76|+23%|+5.42%p|3/1|-27%|-40%|예|
|18|SATL|Aerospace & Defense|$451M|$-0.03 → $0.12|적자→흑자|+5.26%p|3/0|-45%|미산출|예|
|19|BXDC|REIT - Specialty|$1.7B|$0.49 → $1.34|+174%|+5.12%p|2/0|-17%|-70%|-|
|20|NMM|Marine Shipping|$2.5B|$17.33 → $21.48|+24%|+4.84%p|1/0|+0%|-19%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|MSTR|Software - Application|$40.8B|$5.21 → $21.35|+310%|+16.72%p|3/2|-14%|-79%|-|
|2|CVI|Oil & Gas Refining & Marketing|$4.2B|$2.19 → $8.78|+301%|+17.35%p|5/0|+6%|-74%|예|
|3|DK|Oil & Gas Refining & Marketing|$4.0B|$4.08 → $12.20|+199%|+12.30%p|7/1|+3%|-66%|예|
|4|GKOS|Medical Devices|$14.4B|$0.50 → $1.40|+178%|+0.37%p|10/0|+32%|-53%|예|
|5|CLF|Steel|$6.7B|$0.63 → $1.74|+177%|+9.43%p|5/0|+10%|-60%|예|
|6|BXDC|REIT - Specialty|$1.7B|$0.49 → $1.34|+174%|+5.12%p|2/0|-17%|-70%|-|
|7|SPCX|Aerospace & Defense|$1924.4B|$1.78 → $4.17|+134%|+1.68%p|14/1|+6%|-55%|예|
|8|CLMT|Specialty Chemicals|$2.8B|$1.40 → $3.17|+127%|+5.58%p|2/1|-34%|-71%|-|
|9|TXO|Oil & Gas E&P|$705M|$0.97 → $1.92|+98%|+7.49%p|3/0|-10%|-54%|-|
|10|DINO|Oil & Gas Refining & Marketing|$16.5B|$9.37 → $17.52|+87%|+8.34%p|12/1|+5%|-44%|-|
|11|DHT|Oil & Gas Midstream|$3.5B|$1.87 → $3.34|+79%|+6.88%p|3/0|+8%|-40%|예|
|12|VG|Oil & Gas Midstream|$31.5B|$0.96 → $1.66|+72%|+5.59%p|3/1|-12%|-49%|예|
|13|FRO|Oil & Gas Midstream|$10.1B|$3.72 → $6.24|+68%|+5.57%p|4/1|+4%|-38%|예|
|14|MXL|Semiconductors|$4.7B|$2.58 → $4.30|+66%|+3.34%p|10/0|-21%|-53%|예|
|15|CODI|Conglomerates|$896M|$0.55 → $0.90|+62%|+2.90%p|4/1|+3%|-37%|-|
|16|CHRD|Oil & Gas E&P|$7.6B|$13.73 → $21.39|+56%|+5.34%p|15/1|-4%|-38%|예|
|17|TTMI|Electronic Components|$7.0B|$5.40 → $8.34|+54%|+4.40%p|4/0|-42%|-62%|예|
|18|U|Software - Application|$22.4B|$1.72 → $2.65|+54%|+1.84%p|9/0|+8%|-30%|예|
|19|REPX|Oil & Gas E&P|$946M|$7.89 → $11.94|+51%|+9.46%p|4/0|+13%|-26%|예|
|20|GPRE|Chemicals|$887M|$1.56 → $2.35|+50%|+6.25%p|2/1|-22%|-48%|-|

전체 결과: `data/processed/revision_screen/20261118T074219Z_44260623322-1.json.gz`
