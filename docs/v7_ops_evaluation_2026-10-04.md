# v7 운영 검증 — 2026-09-29 ~ 10-04 정상 일간 6회 (Gemini 원문 초안)

- 평가 대상: KST 9/29~10/4 정상 일간 실행 6건의 candidate_context 단계
- 평가일: 2026-10-04 KST (Claude)
- 근거: [K 인수인계](k_handoff_2026-09-27.md) 7절 "9/29 정상 실행이 v7로 도는지 확인", [I3-2 평가](i3_live_evaluation_2026-09-27.md) 4~6절의 Codex 결정 요청 3건
- 새 모델·SEC 요청 없이 평가했다. GitHub API(실행·job·artifact)와 artifact 안의 감사 사본(원문 블록 포함)만 읽었다. 저장소 코드·운영 원장은 바꾸지 않았다.

**요약**

- **v7은 6일 모두 실제로 적용됐다.** 단계 버전 `context-v7`, 감사 사본 36/36이 `context-check-v7`이다.
- v7에서 고친 두 가지(문장 첫 동사를 사업체로 오인, 비교 문장 반대편 기간)는 운영에서도 의도대로 동작했다. 새로 생긴 오수용은 없다.
- 기계 검증을 통과한 문장 56개(주장 40, 반대 근거·한계 16)를 원문과 모두 대조했다.
  - **중대 수치 오류 1건이 카드에 노출 중이다.** CLBK의 "순이자이익: $9.2 million"은 실제로는 증가분이다. 원문의 수준값은 $62.9 million이다.
  - 증가분을 수준값처럼 보이게 표시한 문장이 1건 더 있다(PBF 특별항목 효과). 다만 설명 문구가 증가분임을 밝힌다.
  - 기간이 빠진 가이던스 3건(TEAM)이 있다.
  - 나머지 51건은 수치·주체·기간이 원문과 맞다.
- 검증기에는 **'변화량 vs 수준값' 검사가 없다.** 이 상태에서 과잉 거부만 풀면 오류가 늘어난다(5절 오프라인 재검증에서 DAN 2건 확인).
- 기존 결정 요청 3건은 운영에서 모두 다시 나타났다.
  - AXTI 과잉 거부가 9/30에 재발했다.
  - 카드 앞 3개 문제: CLBK 카드의 3개에 위 오류 문장이 들어간다.
  - 반대 근거: 수용 16건 중 12건이 비GAAP 면책 같은 상투 문구다. 일회성 경고는 대부분 거부됐다.
- 별도 운영 문제: Gemini 503으로 10/1 2건, 10/4 6건 전부가 실패했다(36건 중 8건).

## 1. 실행 확인 (GitHub 증거)

10/1 run을 빼면 모두 conclusion success다. 10/1 run은 extract 단계 실패로 workflow 결론이 failure다(8절, context 단계는 성공).

| KST 일자 | run (attempt 1) | event | checkout SHA | context 단계 | 감사 사본 |
|---|---|---|---|---|---|
| 9/29 | [36528079469](https://github.com/onepuhch/research/actions/runs/36528079469) | schedule | 73e274a | context-v7, complete | 6, 전부 v7 |
| 9/30 | [36674489444](https://github.com/onepuhch/research/actions/runs/36674489444) | schedule | 63668b7 | context-v7, complete | 6, 전부 v7 |
| 10/1 | [36822997450](https://github.com/onepuhch/research/actions/runs/36822997450) | schedule | f555a68 | context-v7, partial | 6, 전부 v7 |
| 10/2 | [36880974655](https://github.com/onepuhch/research/actions/runs/36880974655) | workflow_dispatch(PC 타이머, 00:01 KST) | 78d7f7c | context-v7, complete | 6, 전부 v7 |
| 10/3 | [37099766046](https://github.com/onepuhch/research/actions/runs/37099766046) | schedule | 2734436 | context-v7, complete | 6, 전부 v7 |
| 10/4 | [37181539693](https://github.com/onepuhch/research/actions/runs/37181539693) | schedule | 66398f9 | context-v7, partial | 6, 전부 v7 |

- 6개 SHA는 모두 v7 커밋 31847e6 뒤의 운영 상태 커밋이다. 검증기 코드는 v7과 같다.
- 같은 날의 나머지 실행은 계획이 비어 단계를 건너뛰었다. 하루 1회 실행이 지켜졌다.
- artifact `research-reports-<run>`의 보존 기한은 2026-10-29~11-03이다. 로컬 사본은 평가자 scratchpad에만 있다(저장소 밖).

## 2. 집계

명령: `python tests/live_context_evaluation.py <일자> --audit <artifact>/context_audit/<일자> --run-id <run>-1`

| 일자 | 요청 | 응답 / 실패 | draft_ready | insufficient | no_supported | 수용 주장 | core |
|---|---|---|---|---|---|---|---|
| 9/29 | 6 | 6 / 0 | 2 (AEHR, PBF) | 2 | 2 | 9 | 3 |
| 9/30 | 6 | 6 / 0 | 1 (MPC) | 3 | 2 | 7 | 1 |
| 10/1 | 6 | 4 / 2 (503) | 0 | 2 | 2 | 2 | 0 |
| 10/2 | 6 | 6 / 0 | 1 (CLBK) | 4 | 1 | 15 | 2 |
| 10/3 | 6 | 6 / 0 | 1 (CLF) | 4 | 1 | 7 | 2 |
| 10/4 | 6 | 0 / 6 (503) | 0 | 0 | 0 | 0 | 0 |
| **합계** | **36** | **28 / 8** | **5** | **15** | **8** | **40** | **8** |

- 모든 날에 model_budget candidate_context = 감사 요청 수 = 6이다. 감사 파일 읽기 실패·중복·절단은 0이다.
- 응답 28건의 raw 응답이 모두 보존됐다. CTX 저장도 28/28이다.
- 반대 근거·한계는 16건이 수용됐다. 거부는 주장·한계를 합쳐 123건이다.

## 3. 수용 문장 56건 원문 대조

판정 기준은 I3-2와 같다. 수치·주체·기간이 원문 그대로인지, 그리고 카드에서 읽었을 때 오해가 없는지를 본다.

### 3.1 오류·오해 소지

| # | 기업·일자 | 카드 문장 | 원문 | 판정 |
|---|---|---|---|---|
| 1 | CLBK 10/2 | `net interest income · quarter ended June 30, 2026: $9.2 million — 순이자 이익은 이자 수입 증가와 이자 비용 감소로 늘었다` | "a **$9.2 million increase in** net interest income" (p19). 수준값은 p20 "Net interest income was **$62.9 million**" | **중대 오류.** 증가분을 수준값으로 표시했다. draft_ready 카드의 앞 3개 안에 들어 있어 10/4 카드에도 그대로 노출 중이다. 설명 문구의 원인(이자수입 증가·이자비용 감소)은 인용 문장(p19)이 아니라 p5·p20에 있다 |
| 2 | PBF 9/29 (한계) | `순이익(net income) · second quarter 2026: $159.8 million / $1.32 per share — 특별 비현금 항목이 순이익과 주당 순이익을 증가시켰다` | "increased net income by a net, after-tax **benefit of $159.8 million**" | 머리말만 보면 순이익이 $159.8M로 읽힌다. 설명 문구가 증가 효과임을 밝히므로 경미 |
| 3~5 | TEAM 10/2 | `Total revenue: $1,705 million to $1,715 million` 외 클라우드·데이터센터 성장률 2건 | 가이던스 글머리. 기간은 블록 밖 머리글에만 있다 | 기간이 없다. 4분기 실적 바로 아래 있어 연간 전망으로 오독될 수 있다. 수치 자체는 맞다 |
| 6 | PSX 10/3 | `[Chevron Phillips Chemical Company LLC] full operations · 2027` | CPChem은 Chevron과 50:50 합작사다 | subject를 subsidiary로 분류했다. 카드 표시 이름은 맞아서 경미 |

### 3.2 나머지

- 나머지 50건의 수치·주체·기간은 원문과 맞다.
  - 대상: AMCX, AEHR 2, NBR 4, PBF 2, AXTI, MPC 2, CORT 3, RPAY(KUBRA), CODI 해석, AGL, URGN, CLBK 4, PUBM 2, FSLY, DAN 3, TEAM 실적, SUNC, PGY 2, TXO, CLF 2, 한계 13
- 연도 없이 "second quarter"만 있는 문장(NBR·PUBM·FSLY·SUNC)은 원문 표현 그대로다.
- TXO "decreased oil revenues by $28.5 million"은 수치 문자열에 '감소분'이 들어 있어 오해가 없다.

### 3.3 v7 수정의 운영 확인

- **문장 첫 동사 (IPI류)**: 글머리 첫 동사로 시작하는 문장 3건(SUNC "Reports…", PGY "Raises…", MPC "Advancing MPLX…")이 사업체 오인 없이 수용됐다. 문장 첫 동사 때문에 생긴 subject_scope_conflict는 0건이다.
- **비교 문장 반대편 기간 (PARR류)**: "X, compared to Y for <전년 기간>" 형태가 수용 주장 16건에서 올바르게 처리됐다(CLBK·CLF·DAN·CORT·URGN 등). 전년 수치를 당기 기간으로 함께 적은 주장(AGL R69·R71, DK R16·R17)은 figure_from_another_period로 거부됐다. 의도대로다.
- **v7이 놓치는 기간 형태 (과잉 거부, 오수용 아님)**
  - 기간이 수치 뒤에 오는 나열: TXO "income of $10.0 million for … 2026, a loss of ($3.8) million for the three months ended June 30, 2025". 이 문장의 $3.8M(2025)이 앞쪽 2026에 붙어 거부됐다.
  - "respectively" 대응: SUNC "for the second quarter of 2026 and 2025 included $14 million and $10 million, respectively". 맞는 일회성 비용 문장이 거부됐다.

## 4. 거부 123건 분류 — 맞는 문장이 거부된 유형

| 유형 | 사례(거부 번호는 평가자 덤프 기준) | 원인 (코드) | 수정 범위 |
|---|---|---|---|
| A. **AXTI 재발** (9/30) | GAAP 순이익 $11.1M, 비GAAP 순이익 $11.9M, 비GAAP 매출총이익률 45.0%가 거부됐다. 매출 $47.6M도 거부 → 상태 insufficient_earnings_context | "was **a net income of**" 반복 지표명, "percent **of revenue**" 분모(metric_problem). 매출은 아래 B | I3-2 4절 좁은 수정안 그대로 |
| B. 범위 밖 drivers 태그 | AXTI 매출: drivers `customer_demand`, `productivity` → **bad_tag로 주장 전체 거부** | check_item 마지막의 DRIVERS 집합 검사 | 범위 밖 태그만 버리고 `unknown`으로 대체(사실 아님) |
| C. gaap=`adjusted` 표기 | SUNC 조정 EBITDA $996M·$982M, CLF $286M·3분기 전망 $575M, DINO 3·PARR·DAN 등 10건 | 모델이 허용값(GAAP/non-GAAP/unknown) 밖의 `adjusted`를 써서 gaap_not_as_stated | `adjusted` → `non-GAAP` 동의어 처리 |
| D. **"goodwill"이 전망어로 걸림** | RPAY "Net loss was impacted by … goodwill impairment loss" → guidance_written_as_fact | FORWARD의 `"will "`이 "good**will** "에 부분 일치 | 단어 경계. **명확한 버그** |
| E. 상향어 활용형 | URGN "is **increasing** its … guidance", DAN "revised … upward, **increasing**" → raise_not_in_quote | RAISE의 "increase"는 "increasing"에 부분 일치하지 않는다 | 활용형 추가. **단 F 선행 필요** |
| F. 기간이 머리글에만 있음 | CORT 순이익 $43.0M, MPC 귀속순이익 $5.1B, VLO $3.7B, UCTT 비GAAP 순이익, AMCX 영업이익 등 21건 | period_not_in_source: 인용 문장·블록에 기간 문자열이 없다(글머리 실적 요약) | 설계 변경. 머리글 기간 상속 여부는 Codex 판단 |
| G. 수치 뒤 기간 / respectively | TXO R113, SUNC R106·R107 | 3.3절 | 좁게 가능하나 오수용 위험 검토 필요 |
| H. 지표명 복수형 | AGL "Total Revenues" ↔ 원문 "Total revenue" | metric_not_in_quote 정확 일치 | 경미 |

맞게 거부한 것도 많다. 아래는 의도대로 동작한 사례다.

- 표 행(ambiguous_table_figures) 9건
- 한글로 풀어 쓴 숫자가 있는 설명 문구: CODI "이백삼십오백만 달러"는 틀린 수다
- 인용 문장 짜깁기(RPAY quote_not_in_block)
- 전년 수치 혼입(AGL·DK)
- 모델이 수치 아닌 문구를 figures에 넣은 경우(AGL R73, VLO R54)

## 5. 오프라인 재검증 — 좁은 수정의 효과와 위험

- 저장된 28개 응답을 v7 `validate_draft`에 다시 넣었다. 기준선은 운영 결과와 같다(수용 56, core 주장 9, draft_ready 5).
- 응답을 바꾸거나 함수 상수를 바꿔 본 것은 평가자 scratchpad에서만 했다. 저장소 코드는 바꾸지 않았다.

| 변형 | 수용 | core 주장 | draft_ready | 새로 수용된 문장 판정 |
|---|---|---|---|---|
| v7 기준선 | 56 | 9 | 5 | — |
| C: gaap `adjusted`→non-GAAP | 61 | 11 | 5 | SUNC 3, CLF 2. 4건은 정확하다. 1건(SUNC "guidance: $400 million / $3.5 billion to $3.7 billion")은 증가분과 수준값이 섞였다 |
| B: 범위 밖 drivers → unknown | 57 | 9 | 5 | AXTI 매출 $47.6M. 정확 |
| E: 상향어 활용형 추가 | 58 | 11 | 7 | URGN 영업비용 가이던스 정확. **DAN "sales outlook · full-year: approximately $225 million"은 오류**다. 원문은 "increasing its sales outlook **by** approximately $225 million" |
| B+C+E | 65 | 14 | 7 | 위 합. DAN EBITDA 전망 "$25 million"(실제는 증가분)도 오류 |

**결론**

- 과잉 거부를 푸는 수정(C·E)은 수용과 core 주장을 늘린다.
- 그러나 '변화량 vs 수준값' 오류(CLBK 유형)를 함께 늘린다.
- 따라서 **변화량 검사가 먼저 와야 한다.** 예를 들어 수치 바로 앞의 `by`·`increase of`·`benefit of`, 또는 바로 뒤의 `increase in`·`decrease in` 같은 문구를 본다.
  - 이런 수치를 그 지표의 수준값으로 표시하지 않는다(거부하거나 '증가분'으로 표시).
  - 현재 수용 56건에 적용하면 CLBK·PBF 2건이 걸린다. 오탐은 0건이다(TXO는 수치 문자열이 "decreased … by"를 포함해서 대상이 아님).

## 6. 기존 결정 요청 3건 — 운영 증거 갱신

1. **AXTI 과잉 거부**: 9/30 운영에서 재발했다(4절 A).
   - 맞는 순이익 문장 2건, 이익률 1건, 매출 1건이 모두 거부됐다.
   - 결과적으로 이익 설명이 있는 공시인데도 insufficient로 분류됐다.
   - I3-2 4절의 좁은 수정에 B(drivers)를 함께 넣기를 권한다.
2. **카드 앞 3개만 표시**: 운영 사례가 추가됐다.
   - CLBK(주장 5개): 표시 3개는 순이익(core), **순이자이익 $9.2M(오류)**, NIM(core)이다. 6개월 순이익은 빠졌다.
   - MPC: 표시 2개가 MPLX 자회사 배당 성장, 자본 환원이다. 순이익은 F 유형으로 거부돼 원래 없다.
   - core·현재 기간 우선 정렬 제안은 유지한다. 다만 정렬만으로는 CLBK 오류가 사라지지 않는다. 5절 변화량 검사가 우선이다.
3. **반대 근거 수용률**
   - 수용 16건 중 **12건이 상투 문구**다(비GAAP 면책·정의, 일반 위험 문구: DK·NBR 2·PARR·PUBM 2·FSLY 2·DAN 2·SPT 2).
   - 의미 있는 경고는 4건뿐이다(PBF 특별항목, AGL 회원 감소, CLBK 상쇄 요인 2).
   - 정작 일회성 경고는 거부됐다.
     - RPAY 영업권 손상: D 버그
     - SUNC 일회성 거래비용 $14M·$12M: G
     - CODI 매각 사업 EBITDA $9M 비반복: 설명 문구 숫자, 지표명 불일치
     - VLO 자산손상: 모델 오류
     - PARR 운전자본 역전 전망
   - 카드는 한계 앞 2개를 보여 준다. 그래서 PUBM·FSLY·DAN 카드에는 상투 문구만 표시된다.
   - 제안:
     - (a) D 버그 수정
     - (b) BOILERPLATE에 비GAAP 면책 패턴을 추가해 한계에서 제외하거나 뒤로 정렬
     - (c) 한계 정렬 시 `one_off` 신호(impairment, one-time, non-recurring, special item)를 우선

## 7. 새 결정 요청 (Codex)

우선순위 순서다.

1. **변화량 vs 수준값 검사(신규, 정확성)**
   - CLBK 오류가 카드에 노출 중이다.
   - 수정 전 임시 조치(해당 CTX 무효화 등)가 필요한지 판단해 달라.
   - 이 검사는 검증기 버전을 v8로 올린다.
2. **D "goodwill" 버그**: 단어 경계 수정. 명확한 결함이라 바로 고쳐도 될 것으로 본다.
3. **AXTI(A) + drivers(B) + adjusted(C)**: 좁은 수정이다. 1번 뒤에 적용한다.
4. **상향어 활용형(E)**: 반드시 1번 뒤에 적용한다.
5. **카드 정렬(core 우선)과 한계 정렬/상투 문구 제외**: 카드 버전이 바뀐다.
6. **설계 판단**
   - F(머리글 기간 상속): core 실적 손실이 가장 큰 유형이지만 오수용 위험이 있다.
   - G(수치 뒤 기간·respectively)
   - 설명 문구의 원인이 인용 문장 밖에 있는 문제(CLBK 순이자이익)
7. **운영**: 8절의 5xx 대응.

## 8. 운영 관찰 (v7과 무관)

- **Gemini 503**
  - 10/1에 SPT·SUNC 2건이 실패했다.
  - 10/4에는 6건 전부 실패했다. 06:16:08~06:16:18 약 10초 안에 연속 요청이 나갔다.
  - 실패 건은 24시간 뒤 재시도 대상이 된다(retry_failed_hours). 그날 예산 6은 모두 소진됐다.
  - 첫 5xx 뒤 남은 요청을 멈추는 식의 대응을 검토할 만하다. 다만 같은 날 재시도 경로가 없어 이득은 크지 않다. 판단은 Codex에 맡긴다.
- **10/1 extract 실패**
  - Gemini 재시도 끝에 pending 3이 남았고 exit 1로 끝났다. 그래서 notify가 차단되고 workflow 결론이 failure가 됐다.
  - 같은 날 22:31 KST 실행(36869266328)은 명령 점검뿐이었다.
  - 다음 날 00:01 KST PC 타이머 실행(36880974655)에서 정상 처리됐다.
- **PC 타이머**: 10/2 일간 실행은 PC 타이머 dispatch(00:01 KST)가 GitHub schedule보다 먼저 했다. 중복 실행은 없었다.

## 9. 범위와 한계

- 대조는 감사 사본에 저장된 원문 블록 기준이다. SEC 원문을 다시 받지 않았다.
- 거부 123건은 모두 읽었다. 그러나 '맞는 문장이었는지'의 판정은 4절 유형의 대표 사례만 원문으로 확인했다.
- 카드 화면은 candidates.html에 박힌 JSON으로 확인했다. 브라우저 렌더링은 보지 않았다.
