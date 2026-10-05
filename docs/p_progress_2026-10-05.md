# P 진행 기록 (2026-10-05~)

- 작업자: Claude
- 지시서: [P 지시서](p_o_acceptance_and_discovery_followup_2026-10-05.md)
- 순서: N 정정 → P0 → P1-A → P1-B → P2 → P3

## 기록

### 00:3x KST — 시작

- Codex 문서를 커밋했다(P 지시서, 재현 스크립트, N 정정).
- AEHR 정정에 동의한다.
  - 9/25 bootstrap 입력부터 EPS 예상치가 이미 1.38333이었다.
  - 따라서 N에서 "bootstrap 이후 급상향을 놓쳤다"고 쓴 것은 틀렸다.
- 수정 전 재현(`python docs/p_o_boundary_probe_2026-10-05.py`, 결과는 `data/eval/p_2026-10-05/probe_before.jsonl`): 종료 코드 1. Codex 지적 3건이 Python에서도 그대로 재현됐다.
  - 배당 문장이 업데이트로 통과(`increases`, `expects` 단어 합산)
  - 신용계약 문장이 통과(`agreement`, `capacity` 단어 합산)
  - EX-99 없는 8-K 본문을 읽지 않음
- 10/5 정상 일간은 아직 실행되지 않았다. 15:01Z PC 타이머 요청이 없었다.

### 00:5x KST — P0 완료 (4a2e1c8, context-check-v10 / context-v10)

- **SIG-0900 사용 차단**
  - `config/signal_quarantine.json`에 등록했다: source_id, 문서 URL, 내용 해시, 사유 `subject_other_entity`, 검토 시각
  - 신호를 읽는 7개 경로(`candidate_alerts`·`digest`·`evaluate`·`gen_report`·`notify`·`promote`·`telegram_cmd`)를 `c.read_signals`로 바꿨다. 이 함수가 격리 신호를 뺀다.
  - 원장(`signal_log.csv`, `source_state.json`)은 바꾸지 않았다.
  - 목록이 없거나 깨지면 예외로 멈춘다(빈 목록으로 보지 않음).
  - 중복 확인용 `extract.py`의 원장 읽기만 원본을 그대로 본다.
- **재무제표 주체 판별** (`company_filings.statement_scope`·`block_scopes`·`same_entity`, `subject-check-v1`)
  - "<회사명>, LLC/Inc. … STATEMENT(S) OF … / BALANCE SHEET" 머리글을 찾아, 그 아래 구간의 주체를 정한다.
  - 저장 NOVT 원문: 인용 위치의 주체 = `Runway Buyer, LLC` → 발행사(Novanta)와 다르다고 판정
  - 보관 공시 60건: 머리글 구간 43블록이 모두 발행사 자신 → 오탐 0
- **뉴스 경로** (`extract.evidence_subject_problem`)
  - 다른 회사 재무제표 구간의 인용은 `subject_other_entity`로 거부한다.
  - 제출 회사명을 읽을 수 없으면 `subject_unverified`로 거부한다.
  - 인수 계약 사실(머리글 앞 문장)은 그대로 수용한다.
- **초안 경로** (검증기 v10)
  - 블록에 주체 구간 정보(`scope`)를 붙인다.
  - 발행사 주장이 다른 회사 구간을 인용하면 `subject_other_entity`, 발행사 이름이 없으면 `subject_unverified`로 거부한다.
  - 저장된 v9 초안도 읽을 때 v10으로 재검증한다.
- 시험 7개 추가, 전체 474개 통과

### 01:2x KST — P1-A 완료 (e43b31c, cards-v9)

- **업데이트 판정** (`business_update_judgment`, `update-check-v2`)
  - 한 문장 안에 사업 사건(전망 변경, 고객 계약·수주·수주잔고, 생산능력, 인수, 가격 인상)과 그 수치가 함께 있어야 한다.
  - 배당·자사주·차입·신용계약·보수·소송·임원 문장은 제외한다.
  - P0의 다른 회사 재무제표 구간도 제외한다.
  - 판정은 탐색 적격성일 뿐이며 인과 증명이 아니다.
- **EX-99 없는 8-K**: 업데이트 공시(그리고 EX-99가 전혀 없는 8-K)는 본문도 확인한다. EX-10은 수집하지 않는다.
- **다운로드 순서** (`research` 3단계, 기업당 4개)
  - 1단계: 업데이트, 다운로드 최대 2개
  - 2단계: 실적·정기보고서
  - 3단계: 여유가 남을 때만 못 읽은 업데이트 첨부
  - 무관한 업데이트 첨부 4개가 있어도 실적 발표는 3번째로 받는다(가짜 SEC 전체 경로 시험).
- 업데이트나 다른 회사 재무제표는 '발행사 실적 발표 확보'로 세지 않는다(`own_statements`).
- **캐시 문서**: 저장 blocks로 현재 규칙에 따라 다시 판정하고, 원본 파일은 바꾸지 않는다. 판정 사유는 상태의 `update_checks`에 남긴다.
- **카드 '상향 시기'**
  - 실제 인용 문서의 날짜로 계산한다.
  - 인용되지 않은 더 최신 문서는 `최근 조사 문서 …(채택 근거 없음)`으로 따로 표시하며, 경고를 지우지 않는다.
  - 문구에 '제공처 30일·90일 값 기준 순변화'를 명시한다.
- 재현 스크립트: 수정 후 종료 코드 0(`probe_after_p1a.jsonl`)
- 저장 PBF·AEHR 실적 문서는 계속 실적 근거로 유지된다(시험).
- 시험 7개 추가, O2 시험 3개 갱신, 전체 481개 통과

### 10/5 11:0x KST — P1-B 완료 (4383a3a, cards-v9 유지)

- PC가 꺼져 P1-B 시험과 10/5 실행 감시가 중단됐다. 작업 파일은 보존돼 있었다. 다시 실행한 전체 시험은 486개 통과했다.
- **업종 묶음 세 상태**: 개별 카드 / 업종 제한으로 접힘 / 일반 순위 밖(`outside`). 합계가 count와 같다.
  - 10/4 정유 그룹: 3 + 5 + 1(SUN) = 9
  - `outside`가 없는 예전 스냅샷은 읽을 때 계산한다(`group_states`).
  - 카드 줄·Markdown·/screen이 같은 세 상태를 쓴다.
- **접힌 기업의 현재 요약**: `index.folded_candidates`에 카드 객체로 둔다(순위 없음, 알림 없음).
  - `/candidate`: "업종 묶음에 포함되어 개별 카드는 없습니다 … 최신 스크린 기준 요약" + 카드
  - Markdown: 접힌 기업 목록과 `/candidate` 명령
  - HTML: '업종 제한으로 접힌 기업' 구역
  - 접힌 기존 후보는 '이탈'이 아니라 현재 기업으로 남는다.
- **버전 분리**: 업종 묶음 정보는 관측 메타데이터(`industry_group`, `display_state`)로 옮겼다. 다른 구성원이 바뀌어도 이 기업의 후보 버전(승인 해시)은 그대로다(시험).
- **추적·승인 기업**: 업종 제한으로 접히지 않고 개별 카드에 남는다(순위 표시 '추적').
- **조사 몫**
  - 원문 조사: 하루 10개 중 접힌 기업 최대 2개(`folded_companies_per_day`), 남는 몫은 서로 사용
  - 초안: 그날 남은 모델 요청 중 1개를 접힌 기업용으로 둔다(`folded_drafts_per_day`). 쓰지 않으면 카드 기업이 사용한다.
- 시험 6개 추가, O1 시험 3개 갱신(새 의미), 전체 486개 통과
- 운영: 10/5 정상 일간이 아직 실행 전이라 P0·P1-A·P1-B가 함께 반영될 예정이다(context-v10, cards-v9).
