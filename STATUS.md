# STATUS — investment-research-system

마지막 업데이트: 2026-06-03

## 한 줄 요약
로컬 CSV 기반 투자 후보 **조기 발굴 엔진**. 코어 + metric_log + Discovery Engine Phase 1(Gemini 추출) 작동 확인. GitHub(onepuhch/research) 푸시 완료.

## ▶ 다음 순서 — 우선순위순
1. ✅ **429 throttle** — `extract.py` 호출 간 `sleep`(GEMINI_SLEEP=4s) + 429/503 지수 백오프 재시도(3회). limit 5→3. **검증: 14건 전부 추출, 누락 0.**
2. ✅ **점수 보정** — 프롬프트 규칙 + **메가캡 코드 가드**(소외축 0, 티어 A 금지). 티어를 점수 기반으로 결정론화. **검증: Alphabet A→B 차단됨.**
3. ✅ **EDGAR 정밀화** — 쿼리를 실제 병목 문구로 좁힘. **검증: 쓰레기(AIRO·NRGV) → ALGM·DIOD·ATRO 등 반도체 소형주로 개선.**
4. ✅ **레딧 격리 파이프라인** — `collect_reddit.py`(RSS) → `reddit_watch.csv`(signal_log과 **격리**). SEC 티커목록으로 노이즈 컷. **검증: 200글 → 32후보.**
5. ⏭ **다음: Phase 2 텔레그램 push**(`notify.py`) → **Phase 3 GitHub Actions 매일 cron**.

> 현재 작동 확인됨: collect→extract(Gemini, throttle)→digest + 레딧 별도 라인. `.env`는 깃에 안 올라감(안전).
> 레딧 운영 메모: `.json`은 403 차단 → **`.rss` 사용**. 자동화(Phase 3) 시 데이터센터 IP 차단 가능성 있음.

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

## ★ Discovery Engine (이 프로젝트의 진짜 목표) — Phase 1 ✅
- 전체 브리프: `docs/discovery_engine_design.md`
- **Phase 1 완료·품질패치 완료**: `collect.py`(EDGAR+RSS) · `extract.py`(**Gemini + throttle + 메가캡가드 + 키워드 폴백**) · `digest.py` · `signal_log` 테이블.
- **레딧 격리 라인(별도)**: `collect_reddit.py`(RSS 종목 언급 집계) → `reddit_watch.csv`. 시끄러운 방 → 사람이 보고 진짜만 메인으로 수동 승격. `config/reddit_sources.json`로 서브레딧·제외어 튜닝.
- 다음: Phase 2(텔레그램)→3(자동화).
- 분석 모델: 무료티어 Gemini Flash(`GEMINI_API_KEY` env/.env), 딥다이브는 온디맨드(ChatGPT Plus 수동/Claude).

## 진행 중 / 기록됨
- **Credo (CRDO)** 첫 실(實) 아이디어로 기록 (IDEA-0002, 중기, 병목 확산형) — cold 발굴로 surface
- 발굴 RUN 절차 = AGENTS.md §9 / 개선·역제안 누적 = `IDEAS.md`

## 미해결
- ✅ git 초기화 + GitHub(onepuhch/research) 푸시 완료. 변경 후 `git add -A && git commit -m "..." && git push`(자격증명 캐시돼 자동 업로드).
- 무료티어 429 한도 (→ 다음 순서 1번 throttle로 해결 예정)
- 키 발급: GEMINI ✅(.env), 텔레그램 봇 토큰·FMP는 `.env`에 채워둠(자동화 Phase 2~3에서 사용)

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
