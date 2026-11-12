# 이익 예상치 상향 스크리너

최신 시도: 2026-11-12 16:24 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-11-12 16:24 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7618|7618|0|0|0|
|EPS 예상치|3204|2395|809|0|0|
|업종(후보)|110|110|0|0|0|
|주가 비교(상위)|27|27|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 18곳: COP, EOG, OXY, FANG, PR, OVV, APA, CHRD, SM, MTDR, CRGY, MUR, TALO, NOG, BKV, REPX, TXO, GRNT
- **Semiconductors** 10곳: SKHY, MU, MPWR, CBRS, SWKS, LSCC, SMTC, SIMO, MXL, LASR
- **Oil & Gas Integrated** 10곳: XOM, CVX, SHEL, TTE, BP, EQNR, E, CVE, EC, DEC
- **Oil & Gas Refining & Marketing** 8곳: MPC, VLO, PSX, DINO, PBF, DK, CVI, PARR
- **Oil & Gas Midstream** 8곳: LNG, VG, CQP, FRO, INSW, STNG, DHT, TNK
- **Computer Hardware** 5곳: DELL, SNDK, STX, WDC, SMCI
- **Communication Equipment** 5곳: HPE, LITE, CIEN, VIAV, HLIT
- **Steel** 3곳: NUE, STLD, CLF
- **Software - Application** 3곳: U, SPT, CMRC
- **Electronics & Computer Distribution** 3곳: SNX, ARW, SCSC
- **Software - Infrastructure** 3곳: PRGS, PGY, TLS
- **Banks - Regional** 3곳: HBT, BSVN, SUPV

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$972M|$3.00 → $7.82|+160%|+35.03%p|2/0|-4%|-63%|예|
|2|PBF|Oil & Gas Refining & Marketing|$8.3B|$9.19 → $19.43|+111%|+14.68%p|3/1|-3%|-54%|예|
|3|DK|Oil & Gas Refining & Marketing|$4.1B|$4.75 → $12.04|+154%|+10.86%p|7/1|+3%|-60%|예|
|4|SMCI|Computer Hardware|$20.1B|$3.86 → $6.95|+80%|+10.14%p|5/0|-24%|-58%|예|
|5|CMRC|Software - Application|$305M|$0.31 → $0.68|+118%|+9.99%p|4/0|+67%|-23%|-|
|6|REPX|Oil & Gas E&P|$947M|$7.89 → $11.94|+51%|+9.45%p|2/0|+18%|-22%|예|
|7|DINO|Oil & Gas Refining & Marketing|$17.2B|$9.00 → $17.85|+98%|+8.70%p|12/0|+9%|-45%|예|
|8|CLF|Steel|$7.5B|$0.59 → $1.71|+189%|+8.48%p|4/0|+10%|-62%|예|
|9|CRGY|Oil & Gas E&P|$5.6B|$2.27 → $3.18|+40%|+7.85%p|11/0|-5%|-32%|-|
|10|TXO|Oil & Gas E&P|$773M|$0.97 → $1.92|+98%|+6.83%p|3/0|+1%|-49%|-|
|11|DHT|Oil & Gas Midstream|$3.5B|$1.87 → $3.21|+72%|+6.23%p|3/0|+10%|-36%|-|
|12|SKHY|Semiconductors|$1003.1B|$33.62 → $42.30|+26%|+6.10%p|3/0|-14%|-32%|예|
|13|AMC|Entertainment|$3.1B|$-0.12 → $0.08|적자→흑자|+6.09%p|2/0|+37%|미산출|-|
|14|TNK|Oil & Gas Midstream|$3.1B|$9.12 → $14.45|+58%|+5.99%p|2/0|+4%|-34%|-|
|15|FRO|Oil & Gas Midstream|$10.1B|$3.72 → $6.24|+68%|+5.54%p|4/1|+10%|-34%|예|
|16|UCTT|Semiconductor Equipment & Materials|$2.4B|$3.94 → $6.49|+65%|+5.14%p|4/0|-42%|-64%|예|
|17|MU|Semiconductors|$917.9B|$166.89 → $207.76|+24%|+5.04%p|18/2|-16%|-33%|예|
|18|NMM|Marine Shipping|$2.5B|$17.33 → $21.48|+24%|+4.72%p|3/1|+8%|-13%|예|
|19|BP|Oil & Gas Integrated|$116.6B|$4.21 → $6.03|+43%|+4.03%p|11/1|+6%|-26%|예|
|20|TTMI|Electronic Components|$8.3B|$5.40 → $8.34|+54%|+3.73%p|4/0|-44%|-64%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|SPCX|Aerospace & Defense|$1898.0B|$1.32 → $4.06|+208%|+1.96%p|14/1|-0%|-68%|예|
|2|CLF|Steel|$7.5B|$0.59 → $1.71|+189%|+8.48%p|4/0|+10%|-62%|예|
|3|GKOS|Medical Devices|$14.6B|$0.50 → $1.40|+179%|+0.36%p|10/0|+34%|-52%|예|
|4|DEC|Oil & Gas Integrated|$972M|$3.00 → $7.82|+160%|+35.03%p|2/0|-4%|-63%|예|
|5|DK|Oil & Gas Refining & Marketing|$4.1B|$4.75 → $12.04|+154%|+10.86%p|7/1|+3%|-60%|예|
|6|CMRC|Software - Application|$305M|$0.31 → $0.68|+118%|+9.99%p|4/0|+67%|-23%|-|
|7|PBF|Oil & Gas Refining & Marketing|$8.3B|$9.19 → $19.43|+111%|+14.68%p|3/1|-3%|-54%|예|
|8|DINO|Oil & Gas Refining & Marketing|$17.2B|$9.00 → $17.85|+98%|+8.70%p|12/0|+9%|-45%|예|
|9|TXO|Oil & Gas E&P|$773M|$0.97 → $1.92|+98%|+6.83%p|3/0|+1%|-49%|-|
|10|SMCI|Computer Hardware|$20.1B|$3.86 → $6.95|+80%|+10.14%p|5/0|-24%|-58%|예|
|11|DHT|Oil & Gas Midstream|$3.5B|$1.87 → $3.21|+72%|+6.23%p|3/0|+10%|-36%|-|
|12|SMTC|Semiconductors|$11.7B|$3.92 → $6.67|+70%|+2.20%p|14/0|-11%|-48%|예|
|13|FRO|Oil & Gas Midstream|$10.1B|$3.72 → $6.24|+68%|+5.54%p|4/1|+10%|-34%|예|
|14|MXL|Semiconductors|$5.4B|$2.58 → $4.30|+66%|+2.86%p|10/0|-29%|-58%|예|
|15|TALO|Oil & Gas E&P|$2.6B|$1.13 → $1.88|+66%|+4.87%p|4/2|-2%|-41%|-|
|16|UCTT|Semiconductor Equipment & Materials|$2.4B|$3.94 → $6.49|+65%|+5.14%p|4/0|-42%|-64%|예|
|17|TNK|Oil & Gas Midstream|$3.1B|$9.12 → $14.45|+58%|+5.99%p|2/0|+4%|-34%|-|
|18|GRNT|Oil & Gas E&P|$827M|$0.63 → $0.98|+55%|+5.52%p|3/0|+23%|-21%|-|
|19|TTMI|Electronic Components|$8.3B|$5.40 → $8.34|+54%|+3.73%p|4/0|-44%|-64%|예|
|20|U|Software - Application|$22.0B|$1.72 → $2.59|+51%|+1.76%p|1/0|+7%|-29%|예|

전체 결과: `data/processed/revision_screen/20261112T072442Z_43174666589-1.json.gz`
