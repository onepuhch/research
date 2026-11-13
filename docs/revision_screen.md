# 이익 예상치 상향 스크리너

최신 시도: 2026-11-13 15:57 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-11-13 15:57 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7619|7619|0|0|0|
|EPS 예상치|3222|2407|815|0|0|
|업종(후보)|115|115|0|0|0|
|주가 비교(상위)|26|26|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 18곳: COP, EOG, OXY, FANG, PR, OVV, APA, CHRD, SM, MTDR, CRGY, MUR, TALO, NOG, BKV, REPX, GRNT, TXO
- **Oil & Gas Integrated** 10곳: XOM, CVX, SHEL, TTE, BP, EQNR, E, CVE, EC, DEC
- **Semiconductors** 9곳: SKHY, MU, MPWR, SWKS, LSCC, SMTC, SIMO, MXL, LASR
- **Oil & Gas Refining & Marketing** 8곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR
- **Oil & Gas Midstream** 8곳: LNG, VG, CQP, FRO, INSW, STNG, DHT, TNK
- **Computer Hardware** 6곳: DELL, SNDK, STX, WDC, P, SMCI
- **Communication Equipment** 5곳: HPE, LITE, CIEN, VIAV, HLIT
- **Software - Application** 5곳: MSTR, U, CHYM, MNDY, SPT
- **Steel** 3곳: NUE, STLD, CLF
- **Electronics & Computer Distribution** 3곳: SNX, ARW, SCSC
- **Software - Infrastructure** 3곳: PRGS, PGY, TLS

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$974M|$3.00 → $5.88|+96%|+20.87%p|2/0|-4%|-51%|-|
|2|PBF|Oil & Gas Refining & Marketing|$8.4B|$9.19 → $19.43|+111%|+14.43%p|3/1|-1%|-53%|예|
|3|DK|Oil & Gas Refining & Marketing|$4.1B|$4.75 → $13.63|+187%|+12.97%p|7/1|+4%|-64%|예|
|4|MSTR|Software - Application|$48.4B|$5.20 → $18.85|+262%|+11.93%p|3/2|+23%|-66%|-|
|5|SMCI|Computer Hardware|$17.8B|$3.86 → $6.95|+80%|+11.44%p|5/0|-32%|-62%|예|
|6|REPX|Oil & Gas E&P|$977M|$7.89 → $11.94|+51%|+9.16%p|2/0|+22%|-19%|예|
|7|CLF|Steel|$7.5B|$0.59 → $1.74|+194%|+8.78%p|4/0|+10%|-63%|예|
|8|DINO|Oil & Gas Refining & Marketing|$17.3B|$9.00 → $17.85|+98%|+8.66%p|11/1|+9%|-45%|예|
|9|CRGY|Oil & Gas E&P|$5.8B|$2.15 → $3.18|+48%|+8.60%p|12/0|-1%|-33%|예|
|10|TNK|Oil & Gas Midstream|$3.1B|$9.12 → $15.29|+68%|+6.97%p|3/0|+4%|-38%|-|
|11|TXO|Oil & Gas E&P|$777M|$0.97 → $1.92|+98%|+6.80%p|3/0|+1%|-49%|-|
|12|SKHY|Semiconductors|$971.1B|$32.24 → $41.35|+28%|+6.62%p|3/0|-17%|-36%|-|
|13|GPRE|Chemicals|$961M|$1.56 → $2.46|+57%|+6.59%p|2/1|-13%|-45%|-|
|14|AMC|Entertainment|$3.0B|$-0.12 → $0.08|적자→흑자|+6.24%p|2/0|+34%|미산출|-|
|15|DHT|Oil & Gas Midstream|$3.6B|$1.87 → $3.21|+72%|+6.03%p|3/0|+14%|-34%|-|
|16|FRO|Oil & Gas Midstream|$10.4B|$3.72 → $6.24|+68%|+5.40%p|4/1|+14%|-32%|예|
|17|UCTT|Semiconductor Equipment & Materials|$2.3B|$3.94 → $6.49|+65%|+5.30%p|4/0|-43%|-66%|예|
|18|MU|Semiconductors|$903.4B|$169.12 → $207.76|+23%|+4.84%p|3/1|-18%|-33%|예|
|19|NMM|Marine Shipping|$2.6B|$17.33 → $21.48|+24%|+4.66%p|1/0|+9%|-12%|예|
|20|TTMI|Electronic Components|$8.0B|$5.40 → $8.34|+54%|+3.85%p|4/0|-46%|-65%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|MSTR|Software - Application|$48.4B|$5.20 → $18.85|+262%|+11.93%p|3/2|+23%|-66%|-|
|2|CLF|Steel|$7.5B|$0.59 → $1.74|+194%|+8.78%p|4/0|+10%|-63%|예|
|3|DK|Oil & Gas Refining & Marketing|$4.1B|$4.75 → $13.63|+187%|+12.97%p|7/1|+4%|-64%|예|
|4|GKOS|Medical Devices|$14.6B|$0.50 → $1.40|+179%|+0.36%p|10/0|+33%|-52%|예|
|5|SPCX|Aerospace & Defense|$1900.5B|$1.75 → $4.10|+135%|+1.68%p|14/1|-0%|-58%|예|
|6|PBF|Oil & Gas Refining & Marketing|$8.4B|$9.19 → $19.43|+111%|+14.43%p|3/1|-1%|-53%|예|
|7|DINO|Oil & Gas Refining & Marketing|$17.3B|$9.00 → $17.85|+98%|+8.66%p|11/1|+9%|-45%|예|
|8|TXO|Oil & Gas E&P|$777M|$0.97 → $1.92|+98%|+6.80%p|3/0|+1%|-49%|-|
|9|DEC|Oil & Gas Integrated|$974M|$3.00 → $5.88|+96%|+20.87%p|2/0|-4%|-51%|-|
|10|SMCI|Computer Hardware|$17.8B|$3.86 → $6.95|+80%|+11.44%p|5/0|-32%|-62%|예|
|11|DHT|Oil & Gas Midstream|$3.6B|$1.87 → $3.21|+72%|+6.03%p|3/0|+14%|-34%|-|
|12|SMTC|Semiconductors|$11.1B|$3.95 → $6.67|+69%|+2.28%p|14/0|-15%|-50%|예|
|13|FRO|Oil & Gas Midstream|$10.4B|$3.72 → $6.24|+68%|+5.40%p|4/1|+14%|-32%|예|
|14|TNK|Oil & Gas Midstream|$3.1B|$9.12 → $15.29|+68%|+6.97%p|3/0|+4%|-38%|-|
|15|MXL|Semiconductors|$5.3B|$2.58 → $4.30|+66%|+2.91%p|10/0|-30%|-58%|예|
|16|TALO|Oil & Gas E&P|$2.6B|$1.13 → $1.88|+66%|+4.70%p|4/2|+1%|-39%|-|
|17|UCTT|Semiconductor Equipment & Materials|$2.3B|$3.94 → $6.49|+65%|+5.30%p|4/0|-43%|-66%|예|
|18|GPRE|Chemicals|$961M|$1.56 → $2.46|+57%|+6.59%p|2/1|-13%|-45%|-|
|19|GRNT|Oil & Gas E&P|$856M|$0.63 → $0.98|+55%|+5.33%p|3/0|+27%|-18%|-|
|20|TTMI|Electronic Components|$8.0B|$5.40 → $8.34|+54%|+3.85%p|4/0|-46%|-65%|예|

전체 결과: `data/processed/revision_screen/20261113T065711Z_43381924530-1.json.gz`
