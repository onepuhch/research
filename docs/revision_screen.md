# 이익 예상치 상향 스크리너

최신 시도: 2026-11-19 16:38 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-11-19 16:38 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7609|7609|0|0|0|
|EPS 예상치|3141|2394|747|0|0|
|업종(후보)|117|117|0|0|0|
|주가 비교(상위)|28|28|0|0|0|

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
- **Computer Hardware** 6곳: DELL, STX, SNDK, WDC, P, SMCI
- **Communication Equipment** 5곳: HPE, LITE, CIEN, VIAV, HLIT
- **Software - Application** 4곳: MSTR, U, SMWB, SPT
- **Steel** 3곳: NUE, STLD, CLF
- **Electronics & Computer Distribution** 3곳: SNX, ARW, NSIT
- **Software - Infrastructure** 3곳: PRGS, PGY, TLS
- **Banks - Regional** 3곳: HBT, BSVN, BWFG

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|CVI|Oil & Gas Refining & Marketing|$3.7B|$2.19 → $8.78|+301%|+19.54%p|5/0|-15%|-79%|예|
|2|MSTR|Software - Application|$38.2B|$5.21 → $21.35|+310%|+17.86%p|3/2|-24%|-82%|-|
|3|DK|Oil & Gas Refining & Marketing|$3.7B|$4.08 → $12.20|+199%|+13.46%p|7/1|-16%|-72%|예|
|4|REPX|Oil & Gas E&P|$906M|$7.89 → $11.94|+51%|+9.88%p|4/0|+7%|-29%|예|
|5|CRGY|Oil & Gas E&P|$5.2B|$2.15 → $3.17|+48%|+9.47%p|12/0|-23%|-48%|-|
|6|CLF|Steel|$6.7B|$0.63 → $1.74|+177%|+9.42%p|5/0|+4%|-62%|예|
|7|DINO|Oil & Gas Refining & Marketing|$15.3B|$9.37 → $17.52|+87%|+8.99%p|12/1|-7%|-50%|-|
|8|TXO|Oil & Gas E&P|$691M|$0.97 → $1.92|+98%|+7.64%p|3/0|-12%|-56%|-|
|9|SKHY|Semiconductors|$863.6B|$32.24 → $41.35|+28%|+7.44%p|3/0|-25%|-42%|-|
|10|DHT|Oil & Gas Midstream|$3.4B|$1.87 → $3.34|+79%|+7.10%p|3/0|+5%|-41%|예|
|11|AMC|Entertainment|$2.7B|$-0.12 → $0.08|적자→흑자|+6.92%p|2/0|+18%|미산출|-|
|12|GPRE|Chemicals|$821M|$1.56 → $2.35|+50%|+6.76%p|2/1|-28%|-52%|-|
|13|SMCI|Computer Hardware|$16.1B|$5.33 → $6.95|+30%|+6.64%p|12/0|-35%|-50%|예|
|14|CLMT|Specialty Chemicals|$2.7B|$1.59 → $3.42|+115%|+6.03%p|2/1|-38%|-71%|-|
|15|VG|Oil & Gas Midstream|$30.3B|$0.97 → $1.67|+72%|+5.84%p|3/1|-15%|-51%|예|
|16|MU|Semiconductors|$798.0B|$169.12 → $207.76|+23%|+5.48%p|3/1|-27%|-41%|예|
|17|SATL|Aerospace & Defense|$446M|$-0.03 → $0.12|적자→흑자|+5.32%p|3/0|-49%|미산출|예|
|18|FRO|Oil & Gas Midstream|$9.9B|$3.95 → $6.24|+58%|+5.16%p|4/1|+2%|-36%|예|
|19|NMM|Marine Shipping|$2.4B|$17.33 → $21.48|+24%|+4.99%p|1/0|-6%|-24%|예|
|20|TTMI|Electronic Components|$7.3B|$5.40 → $8.34|+54%|+4.23%p|4/0|-37%|-59%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|MSTR|Software - Application|$38.2B|$5.21 → $21.35|+310%|+17.86%p|3/2|-24%|-82%|-|
|2|CVI|Oil & Gas Refining & Marketing|$3.7B|$2.19 → $8.78|+301%|+19.54%p|5/0|-15%|-79%|예|
|3|DK|Oil & Gas Refining & Marketing|$3.7B|$4.08 → $12.20|+199%|+13.46%p|7/1|-16%|-72%|예|
|4|GKOS|Medical Devices|$13.8B|$0.50 → $1.40|+178%|+0.38%p|10/0|+26%|-55%|예|
|5|CLF|Steel|$6.7B|$0.63 → $1.74|+177%|+9.42%p|5/0|+4%|-62%|예|
|6|SPCX|Aerospace & Defense|$1948.9B|$1.78 → $4.17|+134%|+1.66%p|14/1|+5%|-55%|예|
|7|BXDC|REIT - Specialty|$1.7B|$0.49 → $1.11|+126%|+3.73%p|2/0|-19%|-64%|-|
|8|CLMT|Specialty Chemicals|$2.7B|$1.59 → $3.42|+115%|+6.03%p|2/1|-38%|-71%|-|
|9|TXO|Oil & Gas E&P|$691M|$0.97 → $1.92|+98%|+7.64%p|3/0|-12%|-56%|-|
|10|DINO|Oil & Gas Refining & Marketing|$15.3B|$9.37 → $17.52|+87%|+8.99%p|12/1|-7%|-50%|-|
|11|DHT|Oil & Gas Midstream|$3.4B|$1.87 → $3.34|+79%|+7.10%p|3/0|+5%|-41%|예|
|12|VG|Oil & Gas Midstream|$30.3B|$0.97 → $1.67|+72%|+5.84%p|3/1|-15%|-51%|예|
|13|MXL|Semiconductors|$4.5B|$2.58 → $4.30|+66%|+3.46%p|10/0|-26%|-55%|예|
|14|CODI|Conglomerates|$949M|$0.55 → $0.90|+62%|+2.74%p|4/1|+8%|-34%|-|
|15|FRO|Oil & Gas Midstream|$9.9B|$3.95 → $6.24|+58%|+5.16%p|4/1|+2%|-36%|예|
|16|CHRD|Oil & Gas E&P|$7.3B|$13.86 → $21.41|+54%|+5.49%p|15/1|-7%|-40%|예|
|17|TTMI|Electronic Components|$7.3B|$5.40 → $8.34|+54%|+4.23%p|4/0|-37%|-59%|예|
|18|U|Software - Application|$21.7B|$1.72 → $2.65|+54%|+1.89%p|9/0|+4%|-32%|예|
|19|PTEN|Oil & Gas Drilling|$3.7B|$0.31 → $0.48|+52%|+1.69%p|6/0|-21%|-48%|-|
|20|REPX|Oil & Gas E&P|$906M|$7.89 → $11.94|+51%|+9.88%p|4/0|+7%|-29%|예|

전체 결과: `data/processed/revision_screen/20261119T073847Z_44480870260-1.json.gz`
