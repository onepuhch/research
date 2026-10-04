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
