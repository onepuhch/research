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

### Q1 새 사건 판정·기준 분리 (be69f3e, update-check-v4 / material-update-v2)

- **두 적격성 분리**
  - 검색 적격(`search_eligible`, 기존 사건 문장+수치)과 알림 적격(`alert_eligible`)을 따로 저장한다.
  - 알림 부적격이면 그 이유를 남긴다: `guidance_unchanged`, `guidance_no_prior_value`, `guidance_mixed_range`, `restated_result_or_unchanged`, `period_recount`, `event_date_unknown`.
  - 실적 발표 등 조사한 모든 문서에 판정을 기록한다(`update_checks`).
- **사건 날짜**
  - 문장이 처음 언급하는 날짜를 쓴다(일 또는 월 정밀도). 예: 'In July 2025 … through July 31, 2026' → 2025-07.
  - 문장에 날짜가 없으면, 발표 동사가 있고 보도자료 날짜(dateline)가 있을 때만 그 날짜를 쓴다('document' 정밀도). 그 밖에는 보류한다.
  - `report_date`는 문장의 사건일로 쓰지 않는다.
  - 기준과 비교한다.
    - 기준 이전: 새 사건 아님
    - 기준과 같은 날·같은 달: 보류
    - 제출일보다 뒤: 사건일 아님, 보류
- **알림에서 제외하는 문장**
  - 전망 유지(reaffirm·unchanged·maintain·remain 등)
  - 비교 실적(compared with, prior-year 등)
  - 'as of' 잔액, 'previously announced'
  - 보고 기간 수치(months ended, during the quarter 등)
- **가이던스**
  - 비교 키는 지표, 회계연도, 단위(백만 달러/주당/%), GAAP 여부다.
  - 변경으로 인정하는 경우는 셋이다.
    - 문장 안의 from→to
    - 명시된 변경폭(by $X)
    - 같은 회사의 이전 저장 문서에서 같은 키로 밝힌 최근 전망과 비교한 결과
  - 범위 전망은 양 끝이 같은 방향으로 움직여야 한다. 섞이면 보류한다. 중간값은 쓰지 않는다. 첫 전망은 알리지 않는다.
- **사건 서명**: 발행사, 유형, 그 사건 자체의 수치(가이던스는 기간·지표·기준·새 값), 사건일, 거래 상대방이다.
  - 같은 내용이 다른 날짜에 나오면 재게재로 보고 보류한다.
  - 같은 날짜에 수치가 다르면 모호로 보고 보류한다. 단, 두 상대방이 모두 확인되고 서로 다르면 서로 다른 사건으로 본다.
- **B 기준 분리**
  - EPS 기준을 옮기는 것은 B가 포함된 **sent** 이벤트뿐이다. A만 알린 경우 기준과 첫 확인일을 그대로 둔다.
  - reserved/uncertain 이벤트와 부분(`parts`)이 겹치면 잠근다(`locked_unconfirmed`).
  - failed/released는 예약 때 고정한 내용 그대로 같은 ID로 재시도한다. 조건이 늘어나도 새 ID를 만들지 않는다.
- **원장 이전**
  - material v1 → v2는 한 번만 일어난다(`previous_version` 기록, `candidate_alerts.pre_material-update-v2.json` 백업, persist 대상).
  - PBF 대기 첫 관측(10/5)은 그대로 유지한다. v1에서 발송된 A-only 이벤트가 없으므로 복원할 기준도 없다.
- **저장 자료 대조**
  - 저장 공시 75개에서 v4 알림 적격(기준 비교 전)은 18건이다. 모두 기준(9/25) 이전 날짜이거나 제출일보다 뒤인 약속일이라 A 충족은 0건이다.
  - 재생(`data/eval/q_2026-10-05/material_replay_v2.json`, 스냅샷 10개): 충족은 PBF(B)뿐이다(P와 동일).
  - 재생 스크립트는 이제 빈 대기 상태에서 시작한다. 운영 원장에 대기가 생긴 뒤 그대로 재생하면 9/26 관측이 PBF 대기를 취소해 버리던 문제를 고쳤다.
- 재현 스크립트: Q1 세 건(옛 사건, 전망 유지, A-only 기준 이동)이 해결로 바뀌었다. 남은 열린 경계는 Q3 성과 시작일 1건이다.
- 시험 13개 추가(Q1 필수 목록 포함). P2 시험 고정 자료에 보도자료 날짜를 넣었다. 판정 의미는 같다. 전체 536개 통과.
