# 이익 예상치 상향 스크리너

최신 시도: 2026-09-25 21:11 KST · 상태 **정상** · 마지막 완전 정상 결과: 2026-09-25 21:11 KST

|단계|요청|정상|자료 부족|실패|미시도|
|---|---|---|---|---|---|
|상장 목록(SEC)|1|1|0|0|0|
|Yahoo 접속|1|1|0|0|0|
|시세 일괄 조회|7662|7657|5|0|0|
|EPS 예상치|3239|2412|827|0|0|
|업종(후보)|101|100|1|0|0|
|주가 비교(상위)|30|30|0|0|0|

증권사들이 **내년(다음 회계연도) EPS 예상치**를 최근 90일 동안 얼마나 올렸는지 본다. 내년에 흑자이고, 최근 30일에도 오르고, 올린 증권사가 내린 곳보다 많은 회사만 남긴다.

- **A. 이익 규모 대비 상향:** 예상 EPS 증가분을 주가로 나눈 값(이익수익률 변화, %p). 정유·철강처럼 주가가 이익에 비해 싼 업종에서 크게 나온다.
- **B. 성장률 상향:** 90일 전 예상 대비 증가율. 90일 전에도 주당 $0.25 이상 흑자였던 회사만 본다.
- **주가 90일**은 같은 기간 정규장 종가 변화(Yahoo chart close: split-adjusted, not dividend-adjusted)다. **PER 변화**가 음수면 주가가 EPS 예상 증가를 덜 따라갔다는 뜻이며 저평가의 증거는 아니다. 기간 중 액면분할이 있으면 PER 변화를 산출하지 않는다.
- 7·30·60·90일 전 값은 Yahoo가 제공한 수치다(회계기준 미표시). 우리 원장(metric_log)의 과거 관측으로 쓰지 않는다. 과거 값의 대상 기간이 지금과 같은지는 제공자 자료로 확인할 수 없다.
- 추적 추천이나 매수 추천이 아니다. 후보를 좁히는 첫 단계다.

## 여러 회사가 동시에 상향되는 업종

같은 업종에서 3곳 이상이 동시에 후보에 오르면 업종 전체의 이익 환경이 바뀌는 중일 수 있다.

- **Oil & Gas Refining & Marketing** 9곳: MPC, VLO, PSX, DINO, SUN, PBF, CVI, DK, PARR
- **Oil & Gas Midstream** 6곳: FRO, KNTK, SUNC, DHT, TNK, LPG
- **Semiconductors** 5곳: NVDA, INTC, LSCC, SMTC, MXL
- **Medical Care Facilities** 5곳: THC, LFST, AVAH, AGL, NUTX
- **Software - Application** 5곳: U, FSLY, MNDY, PUBM, SPT
- **Semiconductor Equipment & Materials** 5곳: ACMR, AXTI, KLIC, UCTT, AEHR
- **Computer Hardware** 4곳: DELL, STX, WDC, P
- **Banks - Regional** 4곳: CIB, HBT, CLBK, AMTB
- **Oil & Gas E&P** 4곳: MGY, TALO, KOS, TXO
- **Aerospace & Defense** 3곳: ARXS, VSEC, SPCX
- **Biotechnology** 3곳: CORT, BLTE, URGN
- **Auto Parts** 3곳: MBLY, DAN, DCH
- **Credit Services** 3곳: BFH, AGM, ECPG
- **Software - Infrastructure** 3곳: PGY, SABR, RPAY

> 업종 확인 100/101곳. 업종이 미확인인 후보는 묶음 판단에서 빠졌다.

## A. 이익 규모 대비 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AMCX|Entertainment|$496M|$1.48 → $2.76|+86%|+10.57%p|7/0|+19%|-36%|-|
|2|TALO|Oil & Gas E&P|$2.8B|$-0.04 → $1.66|적자→흑자|+9.99%p|2/0|+28%|미산출|예|
|3|DK|Oil & Gas Refining & Marketing|$4.1B|$2.06 → $7.85|+282%|+8.66%p|6/0|+40%|-63%|예|
|4|PBF|Oil & Gas Refining & Marketing|$8.5B|$6.34 → $12.38|+95%|+8.39%p|4/0|+67%|-14%|예|
|5|MPC|Oil & Gas Refining & Marketing|$109.8B|$23.93 → $47.13|+97%|+5.93%p|12/0|+54%|-22%|예|
|6|AGL|Medical Care Facilities|$1.3B|$-0.62 → $3.20|적자→흑자|+5.03%p|6/0|-36%|미산출|-|
|7|PARR|Oil & Gas Refining & Marketing|$3.8B|$10.00 → $13.84|+38%|+5.00%p|4/1|+40%|+2%|예|
|8|RPAY|Software - Infrastructure|$347M|$0.97 → $1.16|+20%|+4.91%p|2/1|+10%|-8%|-|
|9|VLO|Oil & Gas Refining & Marketing|$110.2B|$21.14 → $38.04|+80%|+4.42%p|7/1|+48%|-18%|예|
|10|DINO|Oil & Gas Refining & Marketing|$18.8B|$7.40 → $11.82|+60%|+4.19%p|9/2|+55%|-3%|예|
|11|TNK|Oil & Gas Midstream|$3.3B|$7.47 → $10.90|+46%|+3.64%p|3/1|+38%|-5%|-|
|12|SPT|Software - Application|$589M|$1.20 → $1.54|+28%|+3.51%p|9/0|+30%|+1%|-|
|13|SUNC|Oil & Gas Midstream|$4.0B|$9.70 → $12.34|+27%|+3.42%p|1/0|+15%|-9%|-|
|14|URGN|Biotechnology|$2.0B|$1.44 → $2.79|+94%|+3.29%p|5/0|+19%|-39%|-|
|15|PGY|Software - Infrastructure|$1.6B|$3.54 → $4.15|+17%|+3.25%p|7/0|+18%|+1%|-|
|16|CODI|Conglomerates|$846M|$0.28 → $0.64|+130%|+3.24%p|4/1|+8%|-53%|예|
|17|LPG|Oil & Gas Midstream|$2.3B|$3.01 → $4.68|+56%|+3.09%p|2/1|+50%|-4%|예|
|18|NBR|Oil & Gas Drilling|$1.3B|$1.11 → $3.61|+224%|+3.01%p|1/0|+0%|-69%|예|
|19|PSX|Oil & Gas Refining & Marketing|$102.6B|$17.28 → $24.90|+44%|+2.98%p|15/1|+49%|+4%|예|
|20|DAN|Auto Parts|$2.9B|$3.38 → $4.19|+24%|+2.94%p|2/1|-3%|-21%|예|

## B. 성장률 상향

|순위|종목|업종|시가총액|내년 EPS 예상 (90일 전 → 지금)|변화|이익수익률 변화|30일 상향/하향|주가 90일|PER 변화|꾸준히 상향|
|---|---|---|---|---|---|---|---|---|---|---|
|1|AEHR|Semiconductor Equipment & Materials|$3.2B|$0.30 → $1.38|+361%|+1.11%p|1/0|+6%|-77%|예|
|2|DK|Oil & Gas Refining & Marketing|$4.1B|$2.06 → $7.85|+282%|+8.66%p|6/0|+40%|-63%|예|
|3|NBR|Oil & Gas Drilling|$1.3B|$1.11 → $3.61|+224%|+3.01%p|1/0|+0%|-69%|예|
|4|AXTI|Semiconductor Equipment & Materials|$5.0B|$0.75 → $2.25|+199%|+1.97%p|4/0|+8%|-64%|예|
|5|CORT|Biotechnology|$12.8B|$1.63 → $4.40|+170%|+2.34%p|2/0|+36%|-50%|-|
|6|IPI|Agricultural Inputs|$482M|$0.57 → $1.41|+148%|+2.36%p|2/0|+4%|-58%|예|
|7|BLTE|Biotechnology|$6.8B|$0.94 → $2.26|+139%|+0.78%p|1/0|+14%|-52%|예|
|8|CODI|Conglomerates|$846M|$0.28 → $0.64|+130%|+3.24%p|4/1|+8%|-53%|예|
|9|MPC|Oil & Gas Refining & Marketing|$109.8B|$23.93 → $47.13|+97%|+5.93%p|12/0|+54%|-22%|예|
|10|PBF|Oil & Gas Refining & Marketing|$8.5B|$6.34 → $12.38|+95%|+8.39%p|4/0|+67%|-14%|예|
|11|URGN|Biotechnology|$2.0B|$1.44 → $2.79|+94%|+3.29%p|5/0|+19%|-39%|-|
|12|AMCX|Entertainment|$496M|$1.48 → $2.76|+86%|+10.57%p|7/0|+19%|-36%|-|
|13|VLO|Oil & Gas Refining & Marketing|$110.2B|$21.14 → $38.04|+80%|+4.42%p|7/1|+48%|-18%|예|
|14|CLBK|Banks - Regional|$1.2B|$0.35 → $0.63|+79%|+2.48%p|1/0|+19%|미산출|예|
|15|PUBM|Software - Application|$845M|$0.49 → $0.81|+67%|+1.75%p|5/0|+47%|-12%|예|
|16|DINO|Oil & Gas Refining & Marketing|$18.8B|$7.40 → $11.82|+60%|+4.19%p|9/2|+55%|-3%|예|
|17|FSLY|Software - Application|$4.3B|$0.39 → $0.63|+60%|+0.88%p|10/0|+56%|-2%|예|
|18|CBRL|Restaurants|$1.2B|$1.16 → $1.85|+60%|+1.33%p|2/0|-2%|-38%|-|
|19|UCTT|Semiconductor Equipment & Materials|$3.5B|$3.77 → $5.87|+56%|+2.74%p|4/0|-36%|-59%|예|
|20|LPG|Oil & Gas Midstream|$2.3B|$3.01 → $4.68|+56%|+3.09%p|2/1|+50%|-4%|예|

전체 결과: `data/processed/revision_screen/20260925T121129Z_36133507734-1.json.gz`
