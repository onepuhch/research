# Claude 재인수 체크포인트 — 2026-09-26

사용자가 Claude에게 작업을 돌려주겠다고 하여 Codex는 여기서 중단한다. **완료/배포 커밋이 아니라 작업 중간 저장이다.** 진행 중 프로세스/테스트 없음. 운영 API·메시지·원장 변경 없고 원격 push도 하지 않았다.

## 시작과 저장

- 기준은 `925b1dd`와 Claude가 미커밋으로 남긴 candidate_context.py/common.py/extract.py 3파일이었다. 기존 변경을 보존해 이어 수정했다.
- `faac736`: H1~H5 중간 구현. `a7db58e`: 첫 체크포인트. 이 문서와 테스트 수정은 후속 로컬 체크포인트 커밋으로 저장한다.
- 브랜치 `codex/research-loop-20260906`. 원격 상태를 재확인한 뒤 push할 것. 검증 전에 정상 배포 완료라고 표시하지 말 것.

## 구현 내용 (검증 미완)

- Claude의 구조화 note_ko/figures/metric/subject 검사를 이어 사용. 직접 인과 explicit_link 금지, 숫자·단위 자유 번역 거부, 복수 문장/지표·불명확 표의 숫자 보수적 거부, 자회사 주체 구분.
- 모델 429 공용 보류, 실제 요청 예약, deadline 전달, 최대 2시도(초안 1시도). Claude 중간 코드의 except 변수 수명 때문에 발생한 UnboundLocalError를 failure 변수로 수정했다.
- SEC 자동 redirect 비활성화, hop별 호스트/예산 검사, 대기 뒤 마감 검사, 요청 전 계수 callback. 문서 HTTP 실패와 no_relevant_document 구분, 부분 성공 quality 기록.
- CIK 목록만 bootstrap하는 refresh_issuers 및 --refresh-issuers. 기존 snapshot/후보 ID 변경 없음. 매핑 복구 시 7일 대기 해제.
- held 상태에서 drafts 실행 차단, 현재 후보/FY 전달. 구버전/수집 실패/기간 불일치 CTX는 현재 카드에서 제외.
- context_verify.py 및 daily_discovery.yml의 별도 context-verification job: Telegram secrets 미제공, RESEARCH_DISABLE_SEND=1, 공용 deliver에서 차단. 선택적 screen refresh, cache-only, 별도 verification run 기록. 이 경로는 **아직 운영 실행 안 함**.

## 실제 실행한 시험

- 최초 Claude 중간 코드에서 전체 283개: 6실패·2오류. 숫자 출력 계약 변경에 따른 구형 fixture와 모델 exception 오류가 주원인이었다.
- 테스트를 새 계약에 맞게 갱신한 중간 전체 실행: 286개, 8실패·1오류. 그 후 아래 수정/부분 재시험을 수행했다. 이 전체 실행 결과를 최종 상태로 혼동하지 말 것.
- 최신 `python -m unittest discover -s tests -p test_candidate_context.py -q`: **27개 통과**.
- 최신 `python -m unittest discover -s tests -p test_candidates.py -q`: **63개 통과**.
- test_model_budget은 최대 2시도 기대와 sleep 주입을 수정했지만 그 뒤 단독/전체 재실행하지 않았다.
- PowerShell→Python 파이프에서 비ASCII가 물음표로 바뀐 부분을 발견해 STATUS와 새 테스트 문구를 수정했다. 이후 명령은 `$OutputEncoding = [System.Text.UTF8Encoding]::new()`와 PYTHONIOENCODING=utf-8을 함께 지정하거나 apply_patch를 사용할 것. 남은 잘못된 문자열도 검색할 것.

## 다음 해야 할 일

1. docs/g_acceptance_followup_2026-09-25.md의 H 요구와 실제 코드를 대조. 이번 중간 구현으로 전부 끝났다고 가정하지 말 것.
2. 전체 테스트부터 재실행하고 실패 해결. 새 H 전용 회귀시험을 추가: 금액/통화/부호/기간/주체, 429 뒤 모든 구성요소 호출 0, deadline timeout 및 재시도, stale+대기 초안 호출 0, 문서 전부 실패/부분 실패, redirect/대기 중 마감/중단 뒤 요청 계수, CIK bootstrap→ID 유지, identity 복구, 전송차단/cache-only.
3. 검토할 남은 한계: HTTP read timeout은 전체 wall-clock 마감과 같지 않음; 모의 client callback과 일일 계수의 멱등성; 문서 partial 품질의 daily/card 전파; 재조사 중단 전 원문 캐시 보존; CTX FY/입력 변경과 현재 카드 연결; 최신 공식 문서 선택 및 주체/기간 의미 검증. 단순히 테스트 기대를 바꿔 통과시키지 말 것.
4. workflow/job 격리와 context_verify의 보호 파일 경로를 schema CSV 실제 경로에 대조. cache-only에서 model/SEC 호출 0과 계수/발송 원장/기존 관측 불변을 시험. 일반 daily 완료 기록을 검증 job이 채우지 않아야 함.
5. 코드/정책 버전 bump 필요 확인(daily_run_state context-v1/cards-v3와 새 생성기 연결). README/인수인계 정리, diff check, Windows 및 CI 환경 회귀.
6. 모두 검증한 뒤 commit/push, Telegram 전송 없는 context_verify 운영 1회, cache-only 반복 확인. gh가 PATH에 없었으므로 기존 인증/실행 경로를 확인하되 비밀값 출력 금지. 제공자 429면 추가 호출 확대 없이 보류를 기록한다.

실종목 임의 추적·추가 Telegram 메시지는 금지한다. 기존 AMCX 영수증/초기 29개/추적 3종목을 보존한다. 사용자가 리셋권을 질문했지만 Codex는 계정 권한/잔여량을 확인하지 못했다.
