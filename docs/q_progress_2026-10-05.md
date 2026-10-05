# Q 진행 기록 (2026-10-05~)

- 작업자: Claude
- 지시서: [Q 지시서](q_p_acceptance_and_reliability_followup_2026-10-05.md)
- 순서: Q0 → Q1 → Q2 → Q3

## 기록

### 10/5 16시대 KST — 시작

- Codex 문서(Q 지시서, 재현 스크립트, `probe_before.json`, STATUS)를 커밋했다.
- 수정 전 재현(`python -X utf8 docs/q_p_boundary_probe_2026-10-05.py`): 종료 코드 1, 열린 경계 6건. Codex 결과와 같다.
- 시작 시점에 진행 중인 Daily Discovery는 없었다.

### Q0-A 주체 판정 (a859a11, subject-check-v2 / context-check-v11 / context-v11 / cards-v10)

- 같은 회사로 인정하는 경우: 구별되는 이름 전체(법인형태·구두점·대소문자·SEC 주 표기 `/TX` 제거)가 발행사 이름이나 그 CIK의 SEC 이전 이름(`formerNames`)과 같을 때만이다.
- 공유 단어가 없으면 다른 회사(`subject_other_entity`), 일부만 겹치면 미확인(`subject_unverified`, 보류)이다.
  - 예: Northstar Acquisition / Northstar Manufacturing → 미확인
  - 예: PBF Holding Company LLC / PBF Energy → 미확인(자회사를 모회사로 합치지 않음)
- 재무제표 머리글 추출에서 앞에 붙은 첨부 표시(`EX-99.1.`)를 떼어낸다. 그 전에는 'EX-99.1. Novanta Inc.'가 머리글로 잡혔다.
- 사업 사건 판정(A)은 확인된 발행사 구간만 사용한다(미확인 구간 제외).
- 저장된 v10 초안은 읽을 때 v11로 재검증하고, 원본은 그대로 둔다.
- 저장 자료 대조: 공시 75개의 재무제표 머리글 3개, 뉴스 원문 114개의 머리글 2개. **판정이 바뀐 건 0건**이다(NOVT/Runway Buyer는 계속 다른 회사).
- 시험 3개를 추가했다(공통 단어·자회사 보류, 정상 표기 차이 수용, 이전 이름 수용, 뉴스 경로 보류).

### Q0-B 저장 복구 (d741168)

- 상태 영역을 경로 규칙으로 정의했다(`persist_state.state_area`).
  - 포함 범위: 데이터 디렉터리(data/processed/), 보관 archive 두 곳, 상태 문서 3개
  - 스테이징 목록은 반드시 이 영역 안에 있어야 한다. 벗어나면 실패한다.
- 원격의 새 커밋이 건드린 모든 경로를 검사한다(`git log -m --no-renames --name-only -z`).
  - 커밋마다 따로 보므로, 이름 변경의 양쪽 경로와 '바꿨다 되돌린' 경우까지 잡힌다.
  - 하나라도 상태 영역이면 다시 올리지 않고 실패한다.
- rebase 1회, push 1회만 한다. 두 번째 경쟁은 실패로 끝난다.
- 실패하면 push하지 못한 커밋을 `reports/generated/unpersisted_state_*.bundle`로 남긴다. 이 파일은 실행 artifact로 업로드되므로, 생성된 상태와 모델 요청 계수를 회수할 수 있다.
- 시험: 실제 임시 bare remote 사용
  - 성공: 코드만 추가, 공백·한글 경로 문서
  - 거부: 상태 수정, 새 DOC, 새 관측, 새 시세, 삭제, 이름 변경, 상태 문서, 추가 후 되돌림, 두 번째 경쟁
- 이미 유실된 10/5 첫 실행의 모델 사용량은 계속 미확인으로 둔다.
- 재현 스크립트: Q0 두 건(`shared_name_word`, `remote_new_state_path`)이 해결로 바뀌었다. 남은 열린 경계는 4건이다. 전체 시험 523개 통과.
