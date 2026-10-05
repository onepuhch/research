# N0·O·P 운영 확인 — 10/5 정상 일간

- 작성: Claude, 2026-10-05 KST(15:1x)
- 대상 실행: `37269585919-1`(schedule, 05:51~06:08Z), code `7e474ed`(P0~P3, persist 수정 포함), policy `0cc76d33876d`
- 같은 시각에 대기하던 두 번째 schedule `37269768914`는 명령 처리만 하고 남은 단계 없이 끝났다(추가 요청 0).
- 앞선 dispatch `37254000539`(02:05Z, `710b256`)는 실행 중 코드 push로 상태가 유실됐다([P 진행 기록](p_progress_2026-10-05.md) 사고 항목). 이번 실행이 10/5 전체를 처음부터 처리했다.
- 확인 방법
  - 원격 상태: `daily_runs.json`, `candidate_alerts.json`, `candidates/index.json`, `candidate_context_state.json`, `company_documents`
  - 실행 산출물: `research-reports-37269585919`의 `context_audit`·HTML·보고서
  - 읽기 전용으로만 확인했다. 수동 재실행·발송은 없다.

## 1. 실행·버전

| 단계 | 상태 | 버전 |
|---|---|---|
| collect·extract·eps·notify·quarterly·screen·prices | success | — |
| context | success | `context-v10` (감사 6건 모두 `context-check-v10`·`context-ko-v4`, code 7e474ed) |
| cards | success | `cards-v9` (index generated 06:06:46Z) |
| alerts | success | 예약·영수증 push 성공(`b164d10`, `74cee4d`) |
| baseline·returns·views·community·weekly_report | success | views `views-v3` |

예전 지시서의 v9/cards-v8 문자열이 아니라 실제 실행 버전을 기록했다.

## 2. 초안(모델) 요청

- 요청 6, 응답 3, 실패 3(HTTP 503, 제공자 과부하)
- 응답 결과
  - URGN: draft_ready, 문장 1(JELMYTO 2026 매출 전망 $97~101M)
  - FSLY: draft_ready, 문장 2(2분기 매출 $183.3M +23%, 연간 전망 상향 언급)
  - UCTT: no_supported_claims
- 실패: CLBK, PUBM, PARR(503). 다음 실행에서 다시 시도한다.
- 10/5 오전 유실 실행이 쓴 요청은 원장에 없다(진행 기록 참조).

## 3. M·N 경계 사례

- **PBF 효과 표시 (M1) — 유지 확인**
  - 한계 문장: `순이익에 미친 영향(net income) · second quarter 2026: $159.8 million(세후 순증가 효과) / $1.32 per share(주당 증가 효과)`
  - 2026-09-29 v7 초안을 v10으로 다시 확인해 통과한 문장만 표시한다.
- **CLBK — 세 경로 모두 격리 유지**
  - 현재 카드: `draft_withheld`, context_hold `CTX-1CD87BF73F9D0762`, 경고 "변화량과 실제 값의 혼동이 확인되어 해당 초안 표시를 중지". 새 초안 요청은 503으로 실패해 새 근거는 아직 없다.
  - 과거 관측 `OB-64236D58D10651AA`·`OB-05E556C1146CB0ED`(cards-v4, 그 CTX 참조): 다시 조립해도 문장은 표시되지 않고 같은 경고가 나온다. `$9.2 million` 0건.
- **AEHR**: v7 초안 재검증 통과 문장 2개(FY27 매출 $130~150M, 비GAAP 순이익률 18~22%)가 표시된다. '상향 시기'에 "최근 30일 몫 100%, 근거 원문 최신 제출 7/14(최근 30일 이전)" 경고가 함께 붙는다.

## 4. O·P 반영

- **업종 묶음 (O1/P1-B)**
  - 카드 33개
  - 정유 9곳: 개별 카드 3(MPC·PBF·DK) + 접힘 5(VLO·PSX·DINO·CVI·PARR) + 일반 순위 밖 1. 카드 줄이 세 상태를 표시한다.
  - `folded_candidates` 5개가 현재 기업으로 남아 있다(/candidate 조회 경로).
- **N의 우선 조사 사례**
  - **OSCR**: 카드에 진입했고 새 발견 알림으로 발송됐다(아래 5절). 원문 연결은 source_linked이며 초안은 아직 없다.
  - **VSEC**: 카드에 진입했다. source_linked.
- **원문 조사 (P1-A/P1-B)**
  - 10곳 모두 success(complete), HTTP 43회
  - 접힌 기업 2곳(VLO, PSX)이 몫 2를 사용했다.
  - 업데이트 판정: 9건 중 적격 1건(VLO)
- **사용 중 발견한 판정 오류 → 수정**
  - VLO 9/18 8-K는 이사 선임 보도자료인데, 'About Valero' 회사 소개 문장("production capacity of approximately 1.2 billion gallons")으로 `capacity` 업데이트에 연결됐다.
  - `update-check-v3`(aa70826)로 고쳤다.
    - 'About <회사>' 머리글 이후는 읽지 않는다.
    - 표 행은 제외한다.
    - 생산능력은 변화 표현이 있을 때만 인정한다.
    - 'acquired intangibles'와 'in order to'는 제외한다.
  - 저장 문서 75개를 재판정했다. v2에서 잘못 통과한 2건(VLO 9/18, PRGS 9/30 표 행)만 거부로 바뀌었고, 나머지 판정은 변하지 않았다.
  - 이 문서는 bootstrap(9/25) 이전 제출이라 P2 재검토 이벤트의 A 조건에도 해당하지 않았다.
- **P0**
  - SIG-0900은 격리 원장 때문에 운영 신호 읽기에서 제외된다.
  - 이번 실행의 extract에서 `subject_other_entity` 거부 기록은 없었다(해당 원문 없음).
- **P2 재검토 변화**
  - 원장에 `material`(material-update-v1)이 생성됐고, P2 이전 원장은 `candidate_alerts.pre_material.json`에 한 번 보관됐다.
  - **PBF 첫 확인일 대기**(`pending`): 9/25 bootstrap 12.375 → 17.655(+42.7%). 다른 KST 날에 한 번 더 유지되면 충족한다. bootstrap 간격 때문에 실제 발송은 빨라야 10/9다.
  - MU: 대상 회계연도가 바뀌어 알림 없이 기준만 다시 잡았다.
  - 충족 0, 취소 0. dry-run 재생(`data/eval/p_2026-10-05/material_replay.json`) 결과와 일치한다.
- **P3 발견 시점 기록**
  - `discovery_timing.json`이 처음 생성됐다(06:08:40Z). 기존 관측은 모두 사후(retrospective)로 표시된다.
  - 127곳: 대표 카드 경험 44, 업종 묶음 5, 일반 순위 밖만 83, 알림 13, bootstrap(알림 없음) 29, 유효 근거 초안 7
  - 시세가 보관된 후보는 0곳이라 성과는 전부 '시세 미수집'이다. 계산하려면 종목당 1회, 약 127회 요청이 필요하다.

## 5. 알림

- 하루 3칸을 모두 썼다. 발송 3, 실패 0, 불확실 0. 재검토 변화 충족은 0이었다.
- 보낸 알림(모두 screen 새 발견)
  - INDV `message_id 154`
  - HIPO `155`
  - OSCR `156`
- 수동 시험 메시지는 보내지 않았다.

## 6. 남은 확인

- CLBK: 새 초안이 나오면 새 근거로 표시되는지 확인한다(옛 CTX와 과거 관측 격리는 유지).
- PBF 재검토 변화: 두 번째 확인과, 10/9 이후 간격이 끝난 뒤의 실제 발송 여부를 본다.
- update-check-v3: 다음 조사부터 적용된다. VLO 상태 항목은 재방문 주기(revisit_days)가 지나 다시 조사할 때 갱신된다. 그 전에도 P2의 A 조건은 저장 blocks를 현재 규칙으로 다시 판정하므로 영향이 없다.
- 503 실패가 연속되는 비율을 계속 관찰한다(회로 차단 작업은 보류 상태 유지).
