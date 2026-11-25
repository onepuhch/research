# 이익 예상치 상향 스크리너

최신 시도: 2026-11-25 17:49 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-11-25 17:49 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7611|7611|0|0|0|
|EPS 예상치|3121|2386|735|0|0|
|업종(후보)|123|123|0|0|0|
|주가 비교(상위)|30|30|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 13곳: COP, EOG, OXY, FANG, PR, OVV, APA, CHRD, CRGY, TALO, REPX, GRNT, TXO
- **Semiconductors** 10곳: NVDA, SKHY, MPWR, CBRS, SWKS, LSCC, SMTC, SIMO, MXL, LASR
- **Oil & Gas Integrated** 9곳: XOM, CVX, SHEL, TTE, BP, EQNR, E, CVE, YPF
- **Oil & Gas Midstream** 8곳: LNG, VG, CQP, FRO, INSW, CMBT, STNG, DHT
- **Computer Hardware** 6곳: DELL, STX, WDC, SNDK, P, SMCI
- **Communication Equipment** 5곳: HPE, LITE, CIEN, VIAV, HLIT
- **Oil & Gas Refining & Marketing** 4곳: PSX, DINO, CVI, DK
- **Steel** 4곳: NUE, STLD, RS, CLF
- **Software - Application** 4곳: MSTR, U, SMWB, SPT
- **Electronics & Computer Distribution** 3곳: SNX, ARW, NSIT
- **Engineering & Construction** 3곳: STRL, LGN, ECG
- **Oil & Gas Drilling** 3곳: PTEN, HP, NBR
- **Specialty Chemicals** 3곳: CLMT, GEVO, ASPN
- **Semiconductor Equipment & Materials** 3곳: AXTI, UCTT, COHU
- **Software - Infrastructure** 3곳: PRGS, PGY, TLS
- **Banks - Regional** 3곳: HBT, BSVN, BWFG

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|MSTR|Software - Application|$33.0B|$1.02 → $21.35|+1995%|+26.21%p|3/2|-44%|-97%|-|
|2|CVI|Oil & Gas Refining & Marketing|$3.5B|$2.19 → $8.02|+266%|+18.53%p|5/0|-21%|-78%|-|
|3|DK|Oil & Gas Refining & Marketing|$3.3B|$4.49 → $11.54|+157%|+12.78%p|7/1|-21%|-70%|-|
|4|CLF|Steel|$6.3B|$0.63 → $2.03|+222%|+12.75%p|5/0|-7%|-71%|예|
|5|REPX|Oil & Gas E&P|$875M|$7.89 → $11.94|+51%|+10.23%p|4/0|+3%|-32%|예|
|6|CRGY|Oil & Gas E&P|$5.1B|$2.15 → $3.07|+43%|+8.77%p|12/0|-23%|-46%|-|
|7|DINO|Oil & Gas Refining & Marketing|$14.6B|$9.37 → $16.82|+80%|+8.63%p|12/1|-11%|-50%|-|
|8|TXO|Oil & Gas E&P|$690M|$0.97 → $1.92|+98%|+7.66%p|3/0|-15%|-57%|-|
|9|AMC|Entertainment|$2.6B|$-0.12 → $0.09|적자→흑자|+7.29%p|2/0|+9%|미산출|예|
|10|SMCI|Computer Hardware|$14.9B|$5.33 → $6.95|+30%|+7.16%p|12/0|-41%|-55%|예|
|11|DHT|Oil & Gas Midstream|$3.4B|$1.88 → $3.35|+78%|+6.88%p|3/0|+10%|-38%|예|
|12|GPRE|Chemicals|$758M|$1.56 → $2.28|+46%|+6.67%p|2/1|-24%|-48%|-|
|13|CLMT|Specialty Chemicals|$2.5B|$1.59 → $3.42|+115%|+6.45%p|2/1|-38%|-71%|-|
|14|SATL|Aerospace & Defense|$385M|$-0.03 → $0.12|적자→흑자|+6.16%p|3/0|-53%|미산출|예|
|15|SKHY|Semiconductors|$789.7B|$33.80 → $40.46|+20%|+5.94%p|3/0|-31%|-42%|-|
|16|VG|Oil & Gas Midstream|$29.9B|$0.97 → $1.67|+72%|+5.92%p|3/1|-18%|-52%|예|
|17|NMM|Marine Shipping|$2.4B|$17.40 → $21.48|+24%|+4.85%p|1/0|-5%|-23%|예|
|18|FRO|Oil & Gas Midstream|$10.6B|$3.95 → $6.23|+58%|+4.79%p|4/1|+9%|-31%|-|
|19|BUR|Asset Management|$738M|$0.54 → $0.69|+28%|+4.50%p|1/0|-22%|-39%|-|
|20|ASPN|Specialty Chemicals|$371M|$-0.18 → $0.02|적자→흑자|+4.34%p|1/0|-15%|미산출|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|MSTR|Software - Application|$33.0B|$1.02 → $21.35|+1995%|+26.21%p|3/2|-44%|-97%|-|
|2|CVI|Oil & Gas Refining & Marketing|$3.5B|$2.19 → $8.02|+266%|+18.53%p|5/0|-21%|-78%|-|
|3|CLF|Steel|$6.3B|$0.63 → $2.03|+222%|+12.75%p|5/0|-7%|-71%|예|
|4|GKOS|Medical Devices|$15.2B|$0.50 → $1.41|+179%|+0.35%p|10/0|+41%|-49%|예|
|5|DK|Oil & Gas Refining & Marketing|$3.3B|$4.49 → $11.54|+157%|+12.78%p|7/1|-21%|-70%|-|
|6|SPCX|Aerospace & Defense|$1708.6B|$1.78 → $4.23|+138%|+1.95%p|14/1|-11%|-62%|예|
|7|BXDC|REIT - Specialty|$1.5B|$0.49 → $1.11|+126%|+4.04%p|2/0|-25%|-67%|-|
|8|CLMT|Specialty Chemicals|$2.5B|$1.59 → $3.42|+115%|+6.45%p|2/1|-38%|-71%|-|
|9|TXO|Oil & Gas E&P|$690M|$0.97 → $1.92|+98%|+7.66%p|3/0|-15%|-57%|-|
|10|DINO|Oil & Gas Refining & Marketing|$14.6B|$9.37 → $16.82|+80%|+8.63%p|12/1|-11%|-50%|-|
|11|DHT|Oil & Gas Midstream|$3.4B|$1.88 → $3.35|+78%|+6.88%p|3/0|+10%|-38%|예|
|12|VG|Oil & Gas Midstream|$29.9B|$0.97 → $1.67|+72%|+5.92%p|3/1|-18%|-52%|예|
|13|MXL|Semiconductors|$3.8B|$2.58 → $4.30|+66%|+4.10%p|10/0|-34%|-60%|예|
|14|CODI|Conglomerates|$992M|$0.55 → $0.90|+62%|+2.62%p|4/1|+17%|-28%|-|
|15|STNG|Oil & Gas Midstream|$4.0B|$5.36 → $8.52|+59%|+3.99%p|8/1|+2%|-36%|예|
|16|CHRD|Oil & Gas E&P|$7.1B|$13.86 → $21.36|+54%|+5.63%p|15/1|-9%|-41%|-|
|17|U|Software - Application|$21.5B|$1.72 → $2.65|+54%|+1.92%p|9/0|+11%|-28%|예|
|18|PTEN|Oil & Gas Drilling|$3.7B|$0.31 → $0.48|+52%|+1.68%p|6/0|-20%|-48%|-|
|19|REPX|Oil & Gas E&P|$875M|$7.89 → $11.94|+51%|+10.23%p|4/0|+3%|-32%|예|
|20|DELL|Computer Hardware|$187.7B|$19.43 → $28.48|+47%|+3.07%p|1/0|-38%|-57%|예|

전체 결과: `data/processed/revision_screen/20261125T084922Z_45579319757-1.json.gz`
