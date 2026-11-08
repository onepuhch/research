# 이익 예상치 상향 스크리너

최신 시도: 2026-11-08 15:17 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-11-08 15:17 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7625|7625|0|0|0|
|EPS 예상치|3184|2391|793|0|0|
|업종(후보)|116|116|0|0|0|
|주가 비교(상위)|28|28|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 17곳: COP, EOG, OXY, FANG, PR, OVV, APA, CHRD, SM, MTDR, MUR, CRGY, NOG, BKV, REPX, TXO, GRNT
- **Semiconductors** 11곳: NVDA, SKHY, MU, MPWR, CBRS, SWKS, LSCC, SMTC, SIMO, MXL, LASR
- **Oil & Gas Integrated** 10곳: XOM, CVX, SHEL, TTE, BP, EQNR, E, CVE, EC, DEC
- **Oil & Gas Refining & Marketing** 9곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR, DKL
- **Oil & Gas Midstream** 7곳: VG, CQP, FRO, INSW, STNG, DHT, TNK
- **Computer Hardware** 5곳: DELL, SNDK, STX, WDC, SMCI
- **Semiconductor Equipment & Materials** 4곳: LRCX, ACMR, UCTT, COHU
- **Communication Equipment** 4곳: HPE, LITE, CIEN, HLIT
- **Steel** 3곳: NUE, STLD, CLF
- **Software - Application** 3곳: U, MNDY, SPT
- **Electronics & Computer Distribution** 3곳: SNX, ARW, SCSC
- **Banks - Regional** 3곳: HBT, BSVN, SUPV

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$898M|$2.42 → $7.40|+206%|+39.23%p|2/0|-11%|-71%|-|
|2|PBF|Oil & Gas Refining & Marketing|$8.0B|$9.19 → $19.43|+111%|+15.22%p|3/1|+2%|-52%|예|
|3|DK|Oil & Gas Refining & Marketing|$3.9B|$3.68 → $10.38|+182%|+10.47%p|7/1|+5%|-63%|예|
|4|SMCI|Computer Hardware|$19.0B|$3.86 → $6.76|+75%|+10.10%p|5/0|-9%|-48%|예|
|5|CLF|Steel|$6.5B|$0.59 → $1.71|+189%|+9.73%p|4/0|-8%|-68%|예|
|6|DINO|Oil & Gas Refining & Marketing|$16.4B|$9.00 → $17.85|+98%|+9.10%p|12/0|+14%|-42%|예|
|7|CRGY|Oil & Gas E&P|$5.4B|$2.27 → $3.18|+40%|+8.12%p|11/0|-8%|-34%|-|
|8|TXO|Oil & Gas E&P|$728M|$0.97 → $1.94|+100%|+7.41%p|3/0|-6%|-53%|-|
|9|DHT|Oil & Gas Midstream|$3.3B|$1.81 → $3.23|+79%|+6.89%p|3/0|+13%|-37%|예|
|10|SKHY|Semiconductors|$898.0B|$33.62 → $42.30|+26%|+6.81%p|3/0|-6%|-25%|예|
|11|AMC|Entertainment|$2.8B|$-0.12 → $0.08|적자→흑자|+6.63%p|2/0|+30%|미산출|-|
|12|GRNT|Oil & Gas E&P|$698M|$0.66 → $1.00|+53%|+6.57%p|3/0|+4%|-32%|예|
|13|TNK|Oil & Gas Midstream|$3.0B|$9.12 → $14.45|+58%|+6.22%p|2/0|+12%|-29%|-|
|14|UCTT|Semiconductor Equipment & Materials|$2.0B|$3.94 → $6.49|+65%|+6.20%p|4/0|-50%|-70%|예|
|15|MU|Semiconductors|$780.7B|$166.89 → $207.76|+24%|+5.92%p|18/2|-20%|-36%|예|
|16|FRO|Oil & Gas Midstream|$10.1B|$3.72 → $6.24|+68%|+5.56%p|4/1|+18%|-30%|예|
|17|VSNT|Entertainment|$4.6B|$6.69 → $8.49|+27%|+5.36%p|1/0|-8%|-28%|-|
|18|SPT|Software - Application|$651M|$1.19 → $1.68|+41%|+4.43%p|9/0|+10%|-22%|예|
|19|TTMI|Electronic Components|$7.0B|$5.40 → $8.34|+54%|+4.41%p|4/0|-49%|-67%|예|
|20|WDC|Computer Hardware|$98.7B|$29.34 → $40.40|+38%|+4.20%p|19/0|-40%|-56%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|SPCX|Aerospace & Defense|$1823.5B|$1.24 → $4.04|+226%|+2.09%p|14/1|-3%|-70%|예|
|2|DEC|Oil & Gas Integrated|$898M|$2.42 → $7.40|+206%|+39.23%p|2/0|-11%|-71%|-|
|3|CLF|Steel|$6.5B|$0.59 → $1.71|+189%|+9.73%p|4/0|-8%|-68%|예|
|4|DK|Oil & Gas Refining & Marketing|$3.9B|$3.68 → $10.38|+182%|+10.47%p|7/1|+5%|-63%|예|
|5|GKOS|Medical Devices|$13.3B|$0.50 → $1.40|+179%|+0.40%p|10/0|+24%|-56%|예|
|6|CVI|Oil & Gas Refining & Marketing|$4.2B|$1.91 → $4.55|+138%|+6.92%p|4/0|+18%|-51%|예|
|7|PBF|Oil & Gas Refining & Marketing|$8.0B|$9.19 → $19.43|+111%|+15.22%p|3/1|+2%|-52%|예|
|8|TXO|Oil & Gas E&P|$728M|$0.97 → $1.94|+100%|+7.41%p|3/0|-6%|-53%|-|
|9|PTEN|Oil & Gas Drilling|$3.8B|$0.26 → $0.47|+85%|+2.18%p|6/0|-10%|-51%|예|
|10|DHT|Oil & Gas Midstream|$3.3B|$1.81 → $3.23|+79%|+6.89%p|3/0|+13%|-37%|예|
|11|SMCI|Computer Hardware|$19.0B|$3.86 → $6.76|+75%|+10.10%p|5/0|-9%|-48%|예|
|12|SMTC|Semiconductors|$9.6B|$3.92 → $6.67|+70%|+2.67%p|14/0|-21%|-54%|예|
|13|FRO|Oil & Gas Midstream|$10.1B|$3.72 → $6.24|+68%|+5.56%p|4/1|+18%|-30%|예|
|14|MXL|Semiconductors|$4.5B|$2.58 → $4.30|+66%|+3.49%p|10/0|-28%|-57%|예|
|15|UCTT|Semiconductor Equipment & Materials|$2.0B|$3.94 → $6.49|+65%|+6.20%p|4/0|-50%|-70%|예|
|16|TNK|Oil & Gas Midstream|$3.0B|$9.12 → $14.45|+58%|+6.22%p|2/0|+12%|-29%|-|
|17|TTMI|Electronic Components|$7.0B|$5.40 → $8.34|+54%|+4.41%p|4/0|-49%|-67%|예|
|18|GRNT|Oil & Gas E&P|$698M|$0.66 → $1.00|+53%|+6.57%p|3/0|+4%|-32%|예|
|19|ZYME|Biotechnology|$2.1B|$0.83 → $1.21|+47%|+1.31%p|3/1|+23%|-16%|-|
|20|VSEC|Aerospace & Defense|$4.9B|$5.68 → $8.26|+46%|+1.50%p|4/2|-22%|-46%|예|

전체 결과: `data/processed/revision_screen/20261108T061749Z_42453944270-1.json.gz`
