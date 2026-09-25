# CLAUDE.md

이 프로젝트의 리서치/개발 지침은 **`AGENTS.md` 에 통합**되어 있다(Codex와 공용).
아래 import 로 그대로 적용한다. 지침을 바꿀 때는 `AGENTS.md` 만 수정한다.

@AGENTS.md

---

## Claude Code 전용 메모
- 리서치 결과는 `AGENTS.md`의 "연구 규칙"을 따른다(결론·근거·한계·다음 점검, 사실·가이던스·컨센서스·해석 분리). 매매 행동·목표주가·비중은 범위 밖이다.
- 최신 시장 데이터가 필요하면 WebSearch 로 확인하고 출처를 단다.
- 작업 시작·종료는 `AGENTS.md`의 "작업자 인수인계"를 따른다(STATUS.md 맨 위 인수인계 칸과 git status 확인).
- 설치된 도움 플러그인: `claude-code-setup`(코드베이스 분석 → 자동화 추천, 읽기 전용). 추천이 필요하면 호출.

## Codex 와 협업할 때
- Codex 는 `CLAUDE.md` 를 읽지 않고 `AGENTS.md` 를 읽는다. 두 파일이 어긋나지 않도록 **내용은 항상 `AGENTS.md` 에만** 둔다.
- harness_framework(상위 폴더의 Codex TDD 하네스)는 이 프로젝트에 적용하지 않는다(규모 대비 과함).
