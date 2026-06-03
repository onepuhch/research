# STATUS — investment-research-system

마지막 업데이트: 2026-06-03

## 한 줄 요약
로컬 CSV 기반 투자 리서치 DB + 자동 리포트 생성 시스템. **코어 완성 + 단계 루브릭/상태판 반영**, 실데이터 입력 단계.

## 완료
- `config/schema.json` 단일 진실원천 설계 (컬럼/enum 한 곳에서 관리)
- 4개 테이블: `sectors` · `industry_indicators` · `bottleneck_log` · `investment_review_log`
- 스크립트 4종: `add_entry`(upsert/append/추적 갱신) · `export_tsv`(시트 복붙) · `gen_report`(**board**/weekly/sector/share) · `create_templates`
- **단계 이동 루브릭**(숫자 기준) PRINCIPLES.md 에 정의, 업종별 `다음 단계 트리거`로 덮어쓰기
- **상태판 `gen_report.py board`**: 활성 아이디어 + 정체(14일) 경고
- 컬럼 보정: `확신도→근거 강도`, `포지션 비중` 제거(리서치/실행 분리), `최근 점검일`(자동 bump)·`다음 단계 트리거` 추가
- 예시 5종, 동작 검증 완료 (추적 갱신 시 중복 없음 / enum 오타 거부 / board·리포트 생성 확인)
- 문서: `README.md` · `PRINCIPLES.md` · `AGENTS.md` · `CLAUDE.md`(=@AGENTS.md)

## 로드맵 (합의된 우선순위)
1. ✅ 단계 이동 루브릭 확정
2. ✅ `investment_review_log`에 `최근 점검일` / `다음 단계 트리거` 추가
3. ✅ 상태판 생성 뷰(`gen_report.py board`)
4. ✅ 에이전트 **역할 정의**(설계만) — `AGENTS.md` §7 (Sector Indicator / Bottleneck Scout / EPS Revision / Risk Check / Review)
5. ⏳ 실제 자동화 — **아직 안 함.** 데이터 쌓인 뒤 스킬(`/research`) → 서브에이전트 순으로.

## ✅ metric_log 구현 완료 (Codex, 검증 통과)
- `metric_log` 테이블 + `방향` enum, add_entry 자동보강(이전값 연결·변화율·방향), gen_report `metric` 상세 + 발굴 보드(`--min`).
- 검증: 연속 상향 횟수/자동계산/enum 거부/무회귀 모두 확인. 브리프: `docs/metric_log_design.md`.

## MVP Definition of Done
- [x] 코드(도구) MVP — 발굴/기록/추적/상태판/리포트/내보내기/복기 + metric_log 까지 완성
- [ ] **실데이터 1바퀴 검증** — 실제 아이디어 1건을 발굴→기록→며칠 metric_log→board 단계판정→export 까지 통과 ← **여기가 남음**

## 다음 구현 (Codex) — ★ Discovery Engine (이 프로젝트의 진짜 목표)
- 무료 스택 조기 발굴 엔진. 전체 브리프: `docs/discovery_engine_design.md`
  - signal_log + collect/extract(무료 LLM)/digest/notify(텔레그램) + GitHub Actions 매일 cron
  - upside-shape 스코어카드(티어 A/B) · de-jargon+glossary · 기술 로드맵 · 해외·forward 밸류
  - Phase 1(로컬)→2(푸시)→3(자동화) 순. 좁게 시작, 품질 우선.
- 분석 모델: 무료티어(Gemini Flash)/로컬, 딥다이브는 온디맨드(ChatGPT Plus 수동/Claude).

## 진행 중 / 기록됨
- **Credo (CRDO)** 첫 실(實) 아이디어로 기록 (IDEA-0002, 중기, 병목 확산형) — cold 발굴로 surface
- 발굴 RUN 절차 = AGENTS.md §9 / 개선·역제안 누적 = `IDEAS.md`

## 미해결
- git 미초기화 (버전관리/디프 검토 위해 `git init` 권장 — OneDrive 동기화 충돌 대비)

## 나중 (선택)
- 텔레그램 봇으로 `gen_report.py share` 자동 전송
- Google Sheets API 연동 (현재는 `export_tsv` 수동 복붙으로 충분)
- 유형별 적중률 집계 리포트(복기 정량화) — Review Agent와 연결

## 주요 결정 기록
- **데이터(원장)와 표현(리포트) 분리** → 공유/자동화 확장 대비
- 업종/아이디어 중복 방지 위해 **upsert · idea_id 추적** 채택
- 90→100점 보강 컬럼: 시장 컨센서스 · 내 견해와의 차이(엣지) · 종료 조건(정량) · 근거 강도 · 다음 단계 트리거
- **근거 강도**(객관) 채택, **포지션 비중은 분리**(실행 결정 → 추후 별도 보유 테이블)
- EPS 상향률 vs 주가 상승률은 **동일 기간(기본 3개월)** 비교로 명시
- 상태판은 저장 테이블이 아니라 **생성 뷰**(데이터 중복/desync 방지)
- `harness_framework`(Codex TDD 하네스)는 이 프로젝트에 **적용 안 함**(과함)

## 협업 / 도구 메모
- **Codex 협업**: 지침은 `AGENTS.md` 공용. Claude Code 는 `CLAUDE.md` 가 `@AGENTS.md` 로 가져옴. → 한 파일만 고치면 됨.
- **작업 방식**: 위임형(방향 분명하면 끝까지), "계획만" 요청 시엔 검토 후 진행.
- 플러그인 `claude-code-setup` 설치됨(자동화 추천기, 읽기 전용).

## 열린 질문
- Google Sheet 인증을 언제 붙일지
- 친구 공유용 요약의 톤/범위 (지금은 면책 문구 포함한 짧은 요약)
- 데이터 폴더가 OneDrive 안 → git 버전관리 도입 여부
