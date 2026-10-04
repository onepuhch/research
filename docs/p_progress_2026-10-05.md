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
