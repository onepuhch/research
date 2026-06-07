# notify.py — 텔레그램 푸시 (Discovery Engine Phase 2) 구현 브리프

> **담당: Codex.** 이 문서가 단일 스펙이다. 설계·검토는 Claude, 구현은 Codex.
> 상위 지침은 [AGENTS.md](../AGENTS.md), 발굴 엔진 전체는 [discovery_engine_design.md](discovery_engine_design.md).

## 0. 목적 (한 줄)
`extract.py`가 `signal_log`에 쌓은 신호 중 **그날 새로 나온 티어 A/B만** 텔레그램으로 push 한다.
관망 노이즈는 보내지 않는다. **레딧(`reddit_watch.csv`)은 격리 대상 → 절대 push 하지 않는다.**

## 1. 산출물
- 신규: `scripts/notify.py` (표준 라이브러리만, 외부 패키지 금지 — `urllib` 사용)
- 신규: `data/processed/notify_state.json` (런타임 상태, 아래 5절) — **`.gitignore`에 추가**
- 리팩터: `extract.py`의 `load_dotenv_value()` 를 `scripts/common.py`로 이동해 공용화
  (extract.py·notify.py 둘 다 `common`에서 import). 동작은 동일해야 함(utf-8-sig·따옴표·`export ` 처리 유지).

## 2. 입력
- `signal_log` 전체: `common.read_rows("signal_log")` 사용.
- 자격증명: `.env`/환경변수에서 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (위 공용 `load_dotenv_value`로 읽기).

## 3. 선별 규칙
1. `티어` ∈ {`A`, `B`} 인 행만 (관망 제외).
2. `signal_id` 가 `notify_state.json`의 `pushed` 목록에 **없는** 것만 (= 미전송 신규).
3. 정렬: 티어 A 먼저(A→B), 그 안에서 `upside_score` 내림차순.
4. 보낼 게 없으면 "신규 0건" 출력 후 **exit 0** (cron 친화).

## 4. 메시지 포맷 (텔레그램 `parse_mode=HTML`)
- 헤더 1줄: `📡 발굴 신호 {N}건 · {YYYY-MM-DD}`
- 신호 블록(빈 줄로 구분):
  ```
  <b>[{티어} · {upside_score}점] {종목/티커}</b>
  {테마} · {신호유형} · {단계 추정}
  {특이값 요약}
  <a href="{출처URL}">{출처}</a>
  ```
- **HTML 이스케이프 필수**: 동적 텍스트(종목/요약/테마/출처 등)의 `&`,`<`,`>`를 각각 `&amp;`,`&lt;`,`&gt;`로 치환한 뒤 삽입. URL은 따옴표 안전 처리.
- **길이 분할**: 한 메시지가 ~3500자 넘으면 블록 단위로 끊어 여러 번 `sendMessage`. (텔레그램 4096자 한도 회피)

## 5. 중복 방지 상태 (`data/processed/notify_state.json`)
- 형식: `{"pushed": ["SIG-0007", "SIG-0008", ...]}`
- 파일 없으면 `{"pushed": []}` 로 시작.
- **전송 성공한 신호만** id를 `pushed`에 추가하고 파일 저장. (전송 실패분은 추가 금지 → 다음 런에서 재시도됨)
- JSON은 utf-8로 저장.

## 6. 텔레그램 전송
- 엔드포인트: `POST https://api.telegram.org/bot{TOKEN}/sendMessage`
- JSON 바디: `{"chat_id": CHAT_ID, "text": ..., "parse_mode": "HTML", "disable_web_page_preview": true}`
- `urllib.request`로 POST, `Content-Type: application/json`, timeout 15~20초.
- 응답 JSON의 `ok` 가 true 인지 확인. false/예외면 경고 출력하고 해당 청크 실패 처리(상태 미기록).
- 네트워크 예외(`HTTPError`/`URLError`/`TimeoutError`)는 잡아서 경고 출력, 비정상 종료시키지 말 것.

## 7. CLI 플래그
- `--dry-run` : 전송하지 않고 만들 메시지를 콘솔에 출력. 상태 파일도 안 건드림. **자격증명 없어도 동작해야 함.**
- `--all` : 중복 방지 무시(이미 보낸 것도 다시 전송). 테스트·재발송용.
- (선택) `--min-tier {A|B}` : 기본 B. A만 받고 싶을 때 사용.

## 8. 자격증명/실패 정책
- 토큰 또는 chat_id가 비어 있으면: 경고 출력 후 **exit 0** (단, `--dry-run`은 그대로 출력). cron 체인이 죽지 않게.
- 콘솔 출력은 Windows cp949에서 죽지 않도록 이모지/em-dash 등은 출력 문자열에서 피하거나 안전하게(파일/메시지 본문에는 이모지 OK, **stdout `print`에는 ASCII 위주**).

## 9. 검증 (Codex가 PR/완료 보고 시 수행)
1. `python scripts\notify.py --dry-run` → 현재 `signal_log`의 A/B 신호로 만들 메시지가 콘솔에 보임(전송 X).
2. `python scripts\notify.py` → 텔레그램으로 1회 실제 전송, 사용자 폰에서 수신 확인.
3. 같은 명령 재실행 → "신규 0건(이미 전송됨)" 출력 = **중복 방지 동작 확인**.
4. `python scripts\notify.py --all` → 재전송됨 = 플래그 동작 확인.
5. 토큰을 일시 제거(또는 빈 값)하고 실행 → 경고 + exit 0 (cron 친화) 확인.
6. `extract.py` 가 공용화된 `load_dotenv_value`로도 기존과 동일하게 동작(회귀 없음) 확인.

## 10. 범위 밖 (하지 말 것)
- 레딧(`reddit_watch.csv`) push — 격리 유지.
- 자동 스케줄링(cron) — 그건 Phase 3.
- signal_log 스키마 변경 — 불필요.
