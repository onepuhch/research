# 이익 예상치 상향 스크리너

최신 시도: 2026-11-27 17:47 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-11-27 17:47 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7611|7611|0|0|0|
|EPS 예상치|3165|2396|769|0|0|
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

- **Oil & Gas E&P** 13곳: COP, EOG, OXY, FANG, PR, OVV, APA, CHRD, CRGY, TALO, REPX, GRNT, TXO
- **Semiconductors** 9곳: NVDA, SKHY, MPWR, CBRS, SWKS, LSCC, SMTC, SIMO, LASR
- **Oil & Gas Integrated** 9곳: XOM, CVX, SHEL, TTE, BP, EQNR, E, CVE, YPF
- **Oil & Gas Midstream** 8곳: LNG, VG, CQP, FRO, INSW, CMBT, STNG, DHT
- **Computer Hardware** 6곳: DELL, STX, WDC, SNDK, P, SMCI
- **Oil & Gas Refining & Marketing** 4곳: PSX, DINO, CVI, DK
- **Communication Equipment** 4곳: HPE, LITE, VIAV, HLIT
- **Steel** 4곳: NUE, STLD, RS, CLF
- **Software - Application** 4곳: MSTR, U, SMWB, SPT
- **Engineering & Construction** 4곳: STRL, LGN, ECG, AMRC
- **Electronics & Computer Distribution** 3곳: SNX, ARW, NSIT
- **Oil & Gas Drilling** 3곳: PTEN, HP, NBR
- **Specialty Chemicals** 3곳: CLMT, GEVO, ASPN
- **Semiconductor Equipment & Materials** 3곳: AXTI, UCTT, COHU
- **Banks - Regional** 3곳: HBT, BSVN, BWFG

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|MSTR|Software - Application|$34.0B|$1.02 → $21.35|+1995%|+25.42%p|3/2|-37%|-97%|-|
|2|CVI|Oil & Gas Refining & Marketing|$3.4B|$2.19 → $8.02|+266%|+19.17%p|5/0|-27%|-80%|-|
|3|DK|Oil & Gas Refining & Marketing|$3.2B|$4.49 → $11.54|+157%|+13.35%p|7/1|-27%|-72%|-|
|4|CLF|Steel|$6.4B|$0.63 → $2.03|+222%|+12.40%p|5/0|-3%|-70%|예|
|5|REPX|Oil & Gas E&P|$875M|$7.89 → $11.94|+51%|+10.23%p|4/0|+3%|-32%|예|
|6|DINO|Oil & Gas Refining & Marketing|$14.5B|$9.37 → $16.83|+80%|+8.69%p|12/1|-14%|-52%|-|
|7|CRGY|Oil & Gas E&P|$5.2B|$2.15 → $3.07|+43%|+8.66%p|12/0|-21%|-45%|-|
|8|TXO|Oil & Gas E&P|$685M|$0.97 → $1.92|+98%|+7.71%p|3/0|-15%|-57%|-|
|9|SMCI|Computer Hardware|$15.4B|$5.33 → $6.95|+30%|+6.95%p|12/0|-37%|-52%|예|
|10|DHT|Oil & Gas Midstream|$3.5B|$1.88 → $3.35|+78%|+6.76%p|3/0|+10%|-38%|예|
|11|CLMT|Specialty Chemicals|$2.4B|$1.59 → $3.42|+115%|+6.75%p|2/1|-43%|-74%|-|
|12|AMC|Entertainment|$2.9B|$-0.12 → $0.09|적자→흑자|+6.70%p|2/0|+24%|미산출|예|
|13|GPRE|Chemicals|$758M|$1.56 → $2.28|+46%|+6.67%p|2/1|-27%|-50%|-|
|14|SATL|Aerospace & Defense|$389M|$-0.03 → $0.12|적자→흑자|+6.10%p|3/0|-48%|미산출|예|
|15|FRO|Oil & Gas Midstream|$10.6B|$4.36 → $7.26|+66%|+6.08%p|4/1|+8%|-35%|예|
|16|VG|Oil & Gas Midstream|$29.6B|$0.97 → $1.67|+72%|+5.99%p|3/1|-17%|-52%|예|
|17|SKHY|Semiconductors|$783.7B|$33.80 → $40.44|+20%|+5.98%p|3/0|-31%|-42%|-|
|18|NMM|Marine Shipping|$2.4B|$17.40 → $21.48|+24%|+4.88%p|1/0|-4%|-22%|예|
|19|ASPN|Specialty Chemicals|$378M|$-0.18 → $0.02|적자→흑자|+4.26%p|1/0|-8%|미산출|예|
|20|BUR|Asset Management|$782M|$0.54 → $0.69|+28%|+4.25%p|1/0|-18%|-36%|-|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|MSTR|Software - Application|$34.0B|$1.02 → $21.35|+1995%|+25.42%p|3/2|-37%|-97%|-|
|2|CVI|Oil & Gas Refining & Marketing|$3.4B|$2.19 → $8.02|+266%|+19.17%p|5/0|-27%|-80%|-|
|3|CLF|Steel|$6.4B|$0.63 → $2.03|+222%|+12.40%p|5/0|-3%|-70%|예|
|4|GKOS|Medical Devices|$15.4B|$0.50 → $1.41|+179%|+0.35%p|10/0|+44%|-48%|예|
|5|DK|Oil & Gas Refining & Marketing|$3.2B|$4.49 → $11.54|+157%|+13.35%p|7/1|-27%|-72%|-|
|6|SPCX|Aerospace & Defense|$1730.8B|$1.78 → $4.23|+138%|+1.93%p|14/1|-10%|-62%|예|
|7|BXDC|REIT - Specialty|$1.5B|$0.49 → $1.11|+126%|+4.12%p|2/0|-25%|-67%|-|
|8|CLMT|Specialty Chemicals|$2.4B|$1.59 → $3.42|+115%|+6.75%p|2/1|-43%|-74%|-|
|9|TXO|Oil & Gas E&P|$685M|$0.97 → $1.92|+98%|+7.71%p|3/0|-15%|-57%|-|
|10|DINO|Oil & Gas Refining & Marketing|$14.5B|$9.37 → $16.83|+80%|+8.69%p|12/1|-14%|-52%|-|
|11|DHT|Oil & Gas Midstream|$3.5B|$1.88 → $3.35|+78%|+6.76%p|3/0|+10%|-38%|예|
|12|VG|Oil & Gas Midstream|$29.6B|$0.97 → $1.67|+72%|+5.99%p|3/1|-17%|-52%|예|
|13|FRO|Oil & Gas Midstream|$10.6B|$4.36 → $7.26|+66%|+6.08%p|4/1|+8%|-35%|예|
|14|CODI|Conglomerates|$1.0B|$0.55 → $0.90|+62%|+2.56%p|4/1|+18%|-27%|-|
|15|CHRD|Oil & Gas E&P|$7.1B|$13.86 → $21.36|+54%|+5.64%p|15/1|-9%|-41%|-|
|16|U|Software - Application|$21.4B|$1.72 → $2.65|+54%|+1.92%p|9/0|+11%|-28%|예|
|17|PTEN|Oil & Gas Drilling|$3.8B|$0.31 → $0.48|+52%|+1.64%p|6/0|-20%|-47%|-|
|18|DELL|Computer Hardware|$188.9B|$20.16 → $30.49|+51%|+3.48%p|1/0|-35%|-57%|예|
|19|REPX|Oil & Gas E&P|$875M|$7.89 → $11.94|+51%|+10.23%p|4/0|+3%|-32%|예|
|20|CBRS|Semiconductors|$21.8B|$1.27 → $1.86|+46%|+0.65%p|1/0|-50%|-66%|-|

전체 결과: `data/processed/revision_screen/20261127T084754Z_45968127921-1.json.gz`
