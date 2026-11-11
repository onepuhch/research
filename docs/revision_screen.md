# 이익 예상치 상향 스크리너

최신 시도: 2026-11-11 15:43 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-11-11 15:43 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7619|7619|0|0|0|
|EPS 예상치|3233|2403|830|0|0|
|업종(후보)|109|109|0|0|0|
|주가 비교(상위)|27|27|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 17곳: COP, EOG, OXY, FANG, PR, OVV, APA, CHRD, SM, MTDR, CRGY, MUR, TALO, NOG, REPX, GRNT, TXO
- **Semiconductors** 11곳: NVDA, SKHY, MU, MPWR, CBRS, SWKS, LSCC, SMTC, SIMO, MXL, LASR
- **Oil & Gas Integrated** 10곳: XOM, CVX, SHEL, TTE, BP, EQNR, E, CVE, EC, DEC
- **Oil & Gas Refining & Marketing** 8곳: MPC, VLO, PSX, DINO, PBF, CVI, DK, PARR
- **Oil & Gas Midstream** 7곳: VG, CQP, FRO, INSW, STNG, DHT, TNK
- **Computer Hardware** 5곳: DELL, SNDK, STX, WDC, SMCI
- **Communication Equipment** 5곳: HPE, LITE, CIEN, VIAV, HLIT
- **Steel** 3곳: NUE, STLD, CLF
- **Software - Application** 3곳: U, SPT, CMRC
- **Electronics & Computer Distribution** 3곳: SNX, ARW, SCSC
- **Banks - Regional** 3곳: HBT, BSVN, SUPV

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$948M|$2.42 → $7.63|+216%|+38.90%p|2/0|-5%|-70%|예|
|2|PBF|Oil & Gas Refining & Marketing|$7.8B|$9.19 → $19.43|+111%|+15.53%p|3/1|-11%|-58%|예|
|3|DK|Oil & Gas Refining & Marketing|$3.8B|$4.38 → $11.95|+173%|+12.09%p|7/1|-8%|-66%|예|
|4|SMCI|Computer Hardware|$18.3B|$3.86 → $6.95|+80%|+11.11%p|5/0|-29%|-61%|예|
|5|CMRC|Software - Application|$308M|$0.31 → $0.68|+118%|+9.91%p|4/0|+66%|-24%|-|
|6|DINO|Oil & Gas Refining & Marketing|$16.7B|$9.00 → $17.85|+98%|+8.96%p|12/0|+8%|-46%|예|
|7|CLF|Steel|$7.3B|$0.59 → $1.71|+189%|+8.67%p|4/0|+6%|-63%|예|
|8|CRGY|Oil & Gas E&P|$5.4B|$2.27 → $3.18|+40%|+8.18%p|11/0|-6%|-33%|-|
|9|TXO|Oil & Gas E&P|$761M|$0.97 → $1.94|+100%|+7.08%p|3/0|-3%|-52%|-|
|10|SKHY|Semiconductors|$914.3B|$33.62 → $42.30|+26%|+6.69%p|3/0|-22%|-38%|예|
|11|DHT|Oil & Gas Midstream|$3.4B|$1.87 → $3.25|+74%|+6.64%p|3/0|+8%|-38%|예|
|12|TNK|Oil & Gas Midstream|$3.0B|$9.12 → $14.45|+58%|+6.22%p|2/0|+3%|-35%|-|
|13|GRNT|Oil & Gas E&P|$796M|$0.63 → $1.00|+58%|+6.12%p|3/0|+20%|-24%|-|
|14|AMC|Entertainment|$3.1B|$-0.12 → $0.08|적자→흑자|+6.02%p|2/0|+32%|미산출|-|
|15|FRO|Oil & Gas Midstream|$9.8B|$3.72 → $6.24|+68%|+5.76%p|4/1|+8%|-36%|예|
|16|MU|Semiconductors|$820.4B|$166.89 → $207.76|+24%|+5.64%p|18/2|-24%|-39%|예|
|17|UCTT|Semiconductor Equipment & Materials|$2.2B|$3.94 → $6.49|+65%|+5.46%p|4/0|-50%|-70%|예|
|18|NMM|Marine Shipping|$2.5B|$17.33 → $21.48|+24%|+4.77%p|3/1|+7%|-14%|예|
|19|BP|Oil & Gas Integrated|$114.8B|$4.21 → $6.03|+43%|+4.09%p|11/1|+4%|-27%|예|
|20|TTMI|Electronic Components|$7.6B|$5.40 → $8.34|+54%|+4.07%p|4/0|-48%|-66%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|DEC|Oil & Gas Integrated|$948M|$2.42 → $7.63|+216%|+38.90%p|2/0|-5%|-70%|예|
|2|SPCX|Aerospace & Defense|$1943.3B|$1.32 → $4.06|+208%|+1.92%p|14/1|+1%|-67%|예|
|3|CLF|Steel|$7.3B|$0.59 → $1.71|+189%|+8.67%p|4/0|+6%|-63%|예|
|4|GKOS|Medical Devices|$14.0B|$0.50 → $1.40|+179%|+0.38%p|10/0|+25%|-55%|예|
|5|DK|Oil & Gas Refining & Marketing|$3.8B|$4.38 → $11.95|+173%|+12.09%p|7/1|-8%|-66%|예|
|6|CVI|Oil & Gas Refining & Marketing|$4.3B|$2.32 → $5.57|+140%|+8.39%p|4/0|+9%|-55%|예|
|7|CMRC|Software - Application|$308M|$0.31 → $0.68|+118%|+9.91%p|4/0|+66%|-24%|-|
|8|PBF|Oil & Gas Refining & Marketing|$7.8B|$9.19 → $19.43|+111%|+15.53%p|3/1|-11%|-58%|예|
|9|TXO|Oil & Gas E&P|$761M|$0.97 → $1.94|+100%|+7.08%p|3/0|-3%|-52%|-|
|10|SMCI|Computer Hardware|$18.3B|$3.86 → $6.95|+80%|+11.11%p|5/0|-29%|-61%|예|
|11|DHT|Oil & Gas Midstream|$3.4B|$1.87 → $3.25|+74%|+6.64%p|3/0|+8%|-38%|예|
|12|SMTC|Semiconductors|$10.6B|$3.92 → $6.67|+70%|+2.42%p|14/0|-15%|-50%|예|
|13|FRO|Oil & Gas Midstream|$9.8B|$3.72 → $6.24|+68%|+5.76%p|4/1|+8%|-36%|예|
|14|MXL|Semiconductors|$4.9B|$2.58 → $4.30|+66%|+3.19%p|10/0|-30%|-58%|예|
|15|TALO|Oil & Gas E&P|$2.5B|$1.13 → $1.88|+66%|+5.05%p|4/2|-4%|-42%|-|
|16|UCTT|Semiconductor Equipment & Materials|$2.2B|$3.94 → $6.49|+65%|+5.46%p|4/0|-50%|-70%|예|
|17|CODI|Conglomerates|$898M|$0.46 → $0.74|+60%|+2.31%p|4/1|-3%|-39%|예|
|18|TNK|Oil & Gas Midstream|$3.0B|$9.12 → $14.45|+58%|+6.22%p|2/0|+3%|-35%|-|
|19|GRNT|Oil & Gas E&P|$796M|$0.63 → $1.00|+58%|+6.12%p|3/0|+20%|-24%|-|
|20|TTMI|Electronic Components|$7.6B|$5.40 → $8.34|+54%|+4.07%p|4/0|-48%|-66%|예|

전체 결과: `data/processed/revision_screen/20261111T064311Z_42974035239-1.json.gz`
