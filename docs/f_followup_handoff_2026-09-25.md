# F1~F6 후속 구현 인수인계 — 2026-09-25 (Claude)

대상 지시: [C·D 검토와 후속 지시](d_acceptance_followup_2026-09-25.md). 순서대로 F1 → F6를 각각 별도 커밋으로 구현했다. 운영 결과와 모의 실패 시험을 구분해 적는다.

## 커밋·테스트

| F | 커밋 | 주요 파일 | 코드를 일부러 망가뜨려 검출 확인 |
|---|---|---|---|
| F1 내용 버전·관측 이력 분리 | 0f2bed1 | candidates.py(cards-v2, candidate_observations), promote.py, collect_eps.py, schema.json(json_records), common.validate_record, persist_state.py | 7/7 |
| F2 명령→계획 순서, 미완료 실패 | 4b06cbe | daily_discovery.yml, daily_run_state.py(finish·@cases), telegram_cmd.py | 4/4 |
| F3 뉴스 누락·기업 14일 간격 | 71256f7 | notify.eligible_signals, candidate_alerts.py, research_policy.json | 5/5 |
| F4 전송 판정·원격 예약 | 3983dd5 | notify.deliver, candidate_alerts.py, persist_state.persist, workflow(커밋 신원 선설정) | 7/7 |
| F5 스냅샷 없는 실패의 stale | bb32224 | candidates.screen_attempt_stale | 3/3 |
| F6 승인 재검증·화면 | f6a9862 | candidates.py(approve·추적 표시·이탈 후보·번역 거부), templates/candidates.html | 6/6 |
| CI 환경 격리(테스트) | 6fb23c0 | tests | — |
| 줄바꿈 무관 해시·예산 시작 시각 | 9ed910e | daily_run_state.py, common.py, model_budget.json | — |

테스트: 기존 192개 → 241개, 모두 통과. 공용 테스트 준비 클래스를 분리해, 상속 때문에 같은 테스트가 중복 실행되던 문제를 없앴다. CI 환경 변수(GITHUB_ACTIONS, DAILY_MODE, GITHUB_RUN_ID 등)를 켠 로컬 실행에서도 241개가 통과한다.

## 운영 결과

- run 36139553876: 테스트 단계에서 실패했다. CI가 작업 전체에 내보내는 GITHUB_RUN_ID와 DAILY_MODE를 테스트가 읽어서, 모의한 "다음 실행"을 같은 실행으로 인식했다. 테스트 단계 이후는 모두 건너뛰어 상태 변경·전송은 없었다. 테스트 격리로 고쳤다(6fb23c0).
- run 36139710587(auto): 계획은 cards(생성기 v2), alerts, baseline(새 @cases 입력), returns, views이며 모두 성공했다.
  - 카드: cards-v1 기록 30개를 관측으로 이관(최초 관측만, migrated 표시). 새 버전 30개, 새 관측 30개. stale 없음.
  - 알림: 선택 0, 격리 0, 발송 0. AMCX 영수증 137과 초기 관측 목록 29개는 유지.
  - finish: 필수 단계 미완료 없음.
- 이 실행 뒤 로컬에서 계획을 계산하니 baseline이 다시 필요하다고 나왔다. 원인은 Windows 체크아웃의 CRLF로 사례 파일 해시가 CI와 달랐던 것이다. 줄바꿈을 정규화한 뒤(9ed910e) 로컬 해시가 CI 기록 `5c4fa9eb…`와 같아졌고 계획은 빈 목록이 됐다. 운영(CI) 판정 자체는 처음부터 맞았다.
- model_budget.json의 counting_since가 13:14 UTC로 잘못 기록돼 있었다. 실제 계수는 12:25 UTC cards 실행부터였으므로 값을 바로잡았고, 이후로는 기존 파일에 시각을 만들어 넣지 않는다.

## 화면 확인 (로컬 Chrome, 1280px·390px)

- 운영 데이터 사본으로 실제 생성한 HTML(거래소를 가짜로 채우지 않음): 카드 30개, 스크립트 오류 0, 가로 넘침 0. 검색·분류·추적 필터, 카드 상세, 영문 원문 표시, `/track CAN-…` 복사 버튼("복사됨 · 텔레그램에 붙여 넣기") 확인.
- "기업은 추적 중·이 가설 미등록" 표시: 운영 데이터에는 해당 경우가 없다. **사본 원장에만** AMCX 다른 가설 행(IDEA-0005, 운영 원장 아님)을 넣어 확인했다. 필터 1건, `/history`와 `/track` 둘 다 표시.
- "최근 목록에서 빠진 후보": 운영 데이터에는 아직 이탈 후보가 없다. 테스트 입력으로 생성한 HTML에서 2건(조회 자료 없음, 스크린 조건 미충족)을 확인했다.
- 결과물 위치: 저장소의 `docs/candidates.md`와 Actions artifact `reports/generated/candidates.html`(30일 보존). 공개 URL은 없다. GitHub Pages·종목별 페이지는 다음 단계다.

## 모의 실패 시험으로만 확인한 것

- 동일 버전 16일 재관측 후 목록 이탈(마지막 관측일 보존), A→B→A 복원, 주가만 바뀐 관측, 등록·발송 당시 카드 재현, 미래 관측 거부, 오래된 반복 /track의 무쓰기, 해시 파일명과 시간 순서 불일치, 통화 충돌 보류.
- 같은 auto 실행에서 명령 큐의 /track → 계획에 eps·quarterly·prices·cards·alerts·views 포함, 반복 명령 재수집 없음, blocked만 남은 실행의 finish 실패.
- 상위 3개 기존 이벤트 + 4번째 신규, 13일/14일 경계(양방향), CIK·거래소:티커 매핑, 승인 알림 예외, legacy 발송 반영.
- message_id 없음·형식 오류·JSON 배열·응답 중 끊김, 예약 push 실패 → 발송 0, 예약 저장 뒤 중단 → 재발송 0, 영수증 push 실패 → 재발송 0(가짜 원격 재생), 실제 임시 git 원격에서 persist 성공·실패 보고.
- 스냅샷 없이 죽은 screen(started·pending·failed)의 stale, 이후 성공으로 해제, 재렌더로 해제 안 됨.
- 승인 거부(오래된 결과, 카드 생성 뒤 근거 변경, 출처 필드 부족, 자료 부족, 근거 보강 필요), 승인 기록(근거 해시·관측 ID), 승인 시 발송 0.

## 운영에서 아직 확인하지 못한 것

- 예약 push → 발송 → 영수증 push 경로의 실제 실행(오늘은 선택된 알림이 없었다). 실메시지를 검증 목적으로 추가 발송하지 않았다.
- 사용자의 실제 /track CAN과 같은 실행 수집, 추적 추천 승인, 월요일 주간 단계(9/28).

## 지시와 다르게 판단했거나 추가한 점

1. 카드 생성기 버전을 올리면서(cards-v2) 모든 후보에 새 버전이 생겼다. 그래서 타임라인에 v1(이관)→v2가 같은 시각으로 나온다. 같은 시각이면 이관 기록이 앞에 온다.
2. 관측 파일은 하루 약 30개(각 2~3KB)가 쌓인다. 스냅샷(실행당 약 430KB)보다 작지만 보존 기간 결정 때 함께 볼 대상이다.
3. finish 실패는 job을 빨간불로 만든다. 상태 저장 단계는 always()라 그대로 실행된다.
4. 번역 거부 기록은 `translation_rejects.json`(저장 대상)에 남는다. 원문은 문서·HTML 카드에만 보이고 텔레그램 카드에는 넣지 않는다(길이 때문).
