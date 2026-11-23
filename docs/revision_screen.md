# 이익 예상치 상향 스크리너

최신 시도: 2026-11-23 16:52 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-11-23 16:52 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7614|7614|0|0|0|
|EPS 예상치|3096|2375|721|0|0|
|업종(후보)|124|124|0|0|0|
|주가 비교(상위)|28|28|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas E&P** 14곳: COP, EOG, OXY, FANG, PR, OVV, APA, CHRD, SM, CRGY, TALO, REPX, GRNT, TXO
- **Semiconductors** 10곳: NVDA, SKHY, MU, MPWR, CBRS, SWKS, LSCC, SIMO, MXL, LASR
- **Oil & Gas Integrated** 8곳: XOM, CVX, SHEL, TTE, BP, EQNR, E, CVE
- **Oil & Gas Midstream** 8곳: LNG, VG, CQP, FRO, INSW, CMBT, STNG, DHT
- **Computer Hardware** 6곳: DELL, STX, WDC, SNDK, P, SMCI
- **Oil & Gas Refining & Marketing** 5곳: PSX, VLO, DINO, CVI, DK
- **Communication Equipment** 5곳: HPE, LITE, CIEN, VIAV, HLIT
- **Software - Application** 4곳: MSTR, U, SMWB, SPT
- **Electronic Components** 4곳: CLS, FLEX, JBL, TTMI
- **Semiconductor Equipment & Materials** 4곳: ACLS, AXTI, UCTT, COHU
- **Steel** 3곳: NUE, STLD, CLF
- **Electronics & Computer Distribution** 3곳: SNX, ARW, NSIT
- **Engineering & Construction** 3곳: STRL, LGN, ECG
- **Oil & Gas Drilling** 3곳: PTEN, HP, NBR
- **Software - Infrastructure** 3곳: PRGS, PGY, TLS
- **Banks - Regional** 3곳: HBT, BSVN, BWFG

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|MSTR|Software - Application|$32.9B|$5.21 → $21.35|+310%|+20.74%p|3/2|-39%|-85%|-|
|2|CVI|Oil & Gas Refining & Marketing|$3.6B|$2.19 → $8.78|+301%|+20.08%p|5/0|-13%|-78%|예|
|3|DK|Oil & Gas Refining & Marketing|$3.6B|$4.08 → $12.20|+199%|+13.57%p|7/1|-12%|-70%|예|
|4|CLF|Steel|$6.1B|$0.63 → $1.70|+171%|+10.05%p|5/0|-7%|-66%|-|
|5|REPX|Oil & Gas E&P|$908M|$7.89 → $11.94|+51%|+9.86%p|4/0|+10%|-27%|예|
|6|DINO|Oil & Gas Refining & Marketing|$14.8B|$9.37 → $17.52|+87%|+9.32%p|12/1|-6%|-50%|-|
|7|CRGY|Oil & Gas E&P|$5.1B|$2.15 → $3.11|+45%|+9.16%p|12/0|-21%|-46%|-|
|8|SKHY|Semiconductors|$730.3B|$32.24 → $41.35|+28%|+8.80%p|3/0|-35%|-49%|-|
|9|AMC|Entertainment|$2.3B|$-0.12 → $0.09|적자→흑자|+8.37%p|2/0|-3%|미산출|예|
|10|TXO|Oil & Gas E&P|$683M|$0.97 → $1.92|+98%|+7.74%p|3/0|-12%|-56%|-|
|11|SMCI|Computer Hardware|$14.3B|$5.33 → $6.95|+30%|+7.48%p|12/0|-44%|-57%|예|
|12|GPRE|Chemicals|$796M|$1.56 → $2.35|+50%|+6.96%p|2/1|-23%|-49%|-|
|13|DHT|Oil & Gas Midstream|$3.5B|$1.87 → $3.34|+79%|+6.84%p|3/0|+13%|-37%|예|
|14|MU|Semiconductors|$672.6B|$171.02 → $208.83|+22%|+6.36%p|3/1|-36%|-48%|예|
|15|SATL|Aerospace & Defense|$380M|$-0.03 → $0.12|적자→흑자|+6.25%p|3/0|-54%|미산출|예|
|16|CLMT|Specialty Chemicals|$2.7B|$1.59 → $3.42|+115%|+5.99%p|2/1|-35%|-70%|-|
|17|VG|Oil & Gas Midstream|$30.1B|$0.97 → $1.67|+72%|+5.88%p|3/1|-15%|-51%|예|
|18|NMM|Marine Shipping|$2.3B|$17.33 → $21.48|+24%|+5.12%p|1/0|-11%|-28%|예|
|19|FRO|Oil & Gas Midstream|$10.1B|$3.95 → $6.23|+58%|+5.04%p|4/1|+4%|-34%|-|
|20|TTMI|Electronic Components|$6.2B|$5.40 → $8.34|+54%|+4.99%p|4/0|-48%|-66%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|MSTR|Software - Application|$32.9B|$5.21 → $21.35|+310%|+20.74%p|3/2|-39%|-85%|-|
|2|CVI|Oil & Gas Refining & Marketing|$3.6B|$2.19 → $8.78|+301%|+20.08%p|5/0|-13%|-78%|예|
|3|DK|Oil & Gas Refining & Marketing|$3.6B|$4.08 → $12.20|+199%|+13.57%p|7/1|-12%|-70%|예|
|4|GKOS|Medical Devices|$14.0B|$0.50 → $1.40|+178%|+0.38%p|10/0|+31%|-53%|예|
|5|CLF|Steel|$6.1B|$0.63 → $1.70|+171%|+10.05%p|5/0|-7%|-66%|-|
|6|SPCX|Aerospace & Defense|$1735.5B|$1.78 → $4.21|+136%|+1.90%p|14/1|-7%|-61%|예|
|7|BXDC|REIT - Specialty|$1.6B|$0.49 → $1.11|+126%|+4.02%p|2/0|-26%|-67%|-|
|8|CLMT|Specialty Chemicals|$2.7B|$1.59 → $3.42|+115%|+5.99%p|2/1|-35%|-70%|-|
|9|TXO|Oil & Gas E&P|$683M|$0.97 → $1.92|+98%|+7.74%p|3/0|-12%|-56%|-|
|10|DINO|Oil & Gas Refining & Marketing|$14.8B|$9.37 → $17.52|+87%|+9.32%p|12/1|-6%|-50%|-|
|11|DHT|Oil & Gas Midstream|$3.5B|$1.87 → $3.34|+79%|+6.84%p|3/0|+13%|-37%|예|
|12|VG|Oil & Gas Midstream|$30.1B|$0.97 → $1.67|+72%|+5.88%p|3/1|-15%|-51%|예|
|13|MXL|Semiconductors|$3.8B|$2.58 → $4.30|+66%|+4.14%p|10/0|-38%|-62%|예|
|14|CODI|Conglomerates|$902M|$0.55 → $0.90|+62%|+2.89%p|4/1|+4%|-36%|-|
|15|FRO|Oil & Gas Midstream|$10.1B|$3.95 → $6.23|+58%|+5.04%p|4/1|+4%|-34%|-|
|16|CHRD|Oil & Gas E&P|$7.3B|$13.86 → $21.61|+56%|+5.68%p|15/1|-3%|-38%|예|
|17|TTMI|Electronic Components|$6.2B|$5.40 → $8.34|+54%|+4.99%p|4/0|-48%|-66%|예|
|18|U|Software - Application|$19.9B|$1.72 → $2.65|+54%|+2.07%p|9/0|-0%|-35%|예|
|19|PTEN|Oil & Gas Drilling|$3.6B|$0.31 → $0.48|+52%|+1.73%p|6/0|-18%|-46%|-|
|20|REPX|Oil & Gas E&P|$908M|$7.89 → $11.94|+51%|+9.86%p|4/0|+10%|-27%|예|

전체 결과: `data/processed/revision_screen/20261123T075252Z_45134023197-1.json.gz`
