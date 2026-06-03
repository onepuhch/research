# 설계: Discovery Engine (투자 후보 조기 발굴 엔진) — 미구현

> 상태: **설계만.** 구현 담당: Codex. 이 문서만 보고 자족적으로 구현 가능하도록 작성.
> 기존 규약 준수: 컬럼/enum은 `config/schema.json` 단일 원본, CSV는 UTF-8-SIG, 경로는 pathlib.
> 단, **이 엔진(수집/추출/푸시)은 외부 라이브러리·네트워크가 필요**하므로, 기존 CSV 도구(stdlib 전용)와 달리 `requests`/`feedparser`/LLM SDK 사용을 허용한다. (CSV 코어는 그대로 stdlib 유지)

---

## 0. 목적 (AGENTS.md §1·§9 참조)
**시장이 다 알기 전에** 메인 테마의 *다음 병목*과 그 *순수 플레이어*를 찾아 추적한다.
뉴스 요약기/종목 추천기가 아니다. 매일 자동으로 '특이값'을 수집·누적하고, **upside가 큰 후보를 텔레그램으로 푸시**한다.

## 1. 아키텍처 4층
```
[1] Collector  → 무료 소스에서 원문 수집 (EDGAR·RSS·무료API)
[2] Extractor  → LLM이 '특이값' 추출 + 점수 + 한국어 요약 + 용어 풀이
[3] signal_log → 신호 누적 + 종목/테마로 클러스터링
[4] 발굴 보드/푸시 → upside-shape 점수로 랭크 → 텔레그램 다이제스트
        ↓ (강화되면) bottleneck_log → investment_review_log → metric_log (기존 시스템)
```

## 2. 무료 스택 (비용 $0 목표)
| 층 | 선택 | 비고 |
|---|---|---|
| 스케줄러 | **GitHub Actions cron** (`.github/workflows/discovery.yml`, 매일) | 무료 2000분/월. PC 꺼져도 돎 |
| 데이터 | **EDGAR**(full-text search/submissions API) + **RSS**(IR·Substack·Reddit·뉴스) + **FMP/Finnhub 무료티어** | 전부 무료(일일 한도 有) |
| 분석 LLM | **무료티어 Gemini Flash** (env로 모델 교체 가능) 또는 로컬 Ollama | 추출/점수/요약용. 프런티어 불필요 |
| 푸시 | **Telegram Bot API** (`sendMessage`) | 무료. urllib/requests로 호출 |
| 시크릿 | GitHub Secrets: `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, (선택)`FMP_API_KEY` | 코드에 키 하드코딩 금지 |

> **분석 모델 정책**: 매일 자동 추출 = 싼/무료 mini 모델. **딥다이브(forward 밸류·해자 판단)는 사람이 온디맨드**로 ChatGPT Plus(수동) 또는 Claude에. (ChatGPT Plus 구독은 스크립트가 호출 불가 → 자동화엔 무료티어 API 사용)

## 3. signal_log 테이블 (`config/schema.json` 추가)
```json
"signal_log": {
  "type": "log",
  "key": "signal_id",
  "id_prefix": "SIG",
  "columns": ["signal_id", "날짜", "종목/티커", "테마", "신호유형", "특이값 요약", "upside_score", "티어", "단계 추정", "용어 풀이", "출처", "출처URL"]
}
```
enums 추가:
```json
"신호유형": ["가이던스상향", "수주/백로그", "신규고객", "CAPEX", "ASP/가격", "리드타임", "EPS상향", "기술로드맵", "공시(8-K)", "커뮤니티", "기타"],
"티어": ["A", "B", "관망"]
```
- `type: log` 이므로 기존 `add_entry.py` 가 그대로 append 처리(신규 코드 최소).

## 4. 수집 소스 (시작은 **좁게**, 품질 우선)
- **EDGAR**: 8-K(주요 이벤트)·가이던스 관련 공시. full-text search API (무료, User-Agent 헤더 필수, 레이트리밋 준수).
- **RSS 큐레이션**(`config/sources.yaml` 로 관리): AI·반도체 인프라 고신호 Substack(예: 우리가 이미 본 photoncap·globalsemiresearch류, SemiAnalysis 공개 글), 관련 subreddit `.rss`, 기업 IR RSS, Google News RSS 쿼리.
- **FMP/Finnhub 무료티어**: watchlist 종목의 추정치/실적 일부(일일 호출 한도 내).
- **해외(미국) 우선** — 한국 소스(네이버 등)는 쓰지 않음.
- 시작은 **소스 5~10개**만. 돌려보고 신호/노이즈 보며 확장.

## 5. 특이값 추출 규칙 (Extractor 프롬프트 핵심)
수집 원문에서 다음을 잡는다(잡히면 signal_log 1행):
- **변곡 키워드**: "record backlog / sold out / capacity doubling(triple) / pricing up(ASP↑) / supply constrained / new (Nth) customer / design win / guidance raised / prepayment / long-term agreement".
- **숫자 변화**: 가이던스↑, CAPEX, ASP, 리드타임, 수주잔고, EPS 상향, 재고 변화.
- **기술 로드맵**: 800G→1.6T→CPO, 구리→광 등 *기술 진화* 언급(= 병목 이동의 선행지표).
각 신호에:
- **한국어 특이값 요약**(1~2줄), **출처/URL**,
- **용어 풀이**(de-jargon): 처음 보는 기술/용어를 *plain 한국어 + 왜 투자에 중요한지* 1줄. → §8 glossary에도 누적.
- **upside_score / 티어 / 단계 추정** (§6).

## 6. upside-shape 스코어카드 (핵심)
후보를 6축으로 0~2점씩 채점(총 0~12) → 티어:
1. **작은 베이스** (시총/유통 작을수록↑)
2. **이익 변곡** (매출 *가속*, GM 확대, incremental margin↑, EPS 저/적자 베이스)
3. **공급제약 가격결정력** (ASP↑·백로그·리드타임·sold out)
4. **구조적 수요 드라이버** (AI 등 다년 테마 레버리지)
5. **리비전 초기** (forward EPS 막 상향, 주가 미반영, 커버리지 적음)
6. **재평가 촉매** (가이던스 상향·대형 고객·증설·신규 커버리지)

출력: **`upside_score` + 티어(A=10배 모양·극단 / B=3~5배 모양 / 관망) + 예상 시간축 + 아이디어 유형**.
- 10배만 쫓지 않음 — A·B 모두 발굴. 5개 아이디어 유형 전부 허용(A는 사이클/병목 위주, B는 구조적성장·재평가 포함).
- **forward 밸류로 본다**: trailing PER ❌. forward EPS·forward PER, 그리고 '동일 기간(기본 3개월) EPS 상향률 vs 주가 상승률' 갭을 본다.
- **price-context(차트 아님)**: 52주 위치·고점 대비 거리만 *확인용*. TA 지표/패턴은 신호로 쓰지 않음.

## 7. 발굴 보드 + 텔레그램 다이제스트
- `scripts/digest.py`: signal_log 최근분을 **upside_score/티어순**으로 정렬 → 짧은 다이제스트(마크다운/텍스트) 생성.
- `scripts/notify.py`: Telegram `sendMessage` 로 다이제스트 전송. (고신호=즉시, 일반=일일 1회)
- 다이제스트 = **짧게**: 상위 N개 후보 + 특이값 1줄 + 용어 풀이 + 점수/티어 + 출처. (개인 기록, 투자권유 아님 문구)

## 8. 용어집 + 기술 로드맵
- `docs/glossary.md`: 마주친 용어를 *plain 설명 + 왜 중요 + 관련 아이디어*로 누적. Extractor가 새 용어 만나면 append 제안.
- 기술 로드맵 트래킹: 신호유형 "기술로드맵"으로 signal_log에 쌓아, 병목이 다음 어디로 갈지의 선행지표로 사용.

## 9. 기존 시스템 연결
- signal_log(발굴) → 반복 강화된 후보를 **bottleneck_log**(병목 가설)로 → 검증되면 **investment_review_log**(아이디어, 단계 추적) → 숫자 추적은 **metric_log**.
- watchlist 종목의 forward EPS 수동 보완 소스 = **Yahoo Finance / Finviz / Koyfin / 기업 IR**(미국 기준. 네이버 아님).

## 10. 구현 단계 (Phase)
- **Phase 1 (로컬, 자동화 전)**: `signal_log` 스키마 + `scripts/collect.py`(EDGAR+RSS 1~2개) + `scripts/extract.py`(무료 LLM 호출, .env 키) + signal_log 기록 + `scripts/digest.py`(로컬 출력). 수동 실행으로 동작 확인.
- **Phase 2 (푸시)**: `scripts/notify.py`(텔레그램) 연결.
- **Phase 3 (자동화)**: `.github/workflows/discovery.yml`(매일 cron) + GitHub Secrets. 소스 확장.

## 11. 완료 기준 (acceptance)
- Phase 1: `python scripts/collect.py` → 원문 수집, `python scripts/extract.py` → signal_log.csv 생성(UTF-8-SIG)+신호 행, `python scripts/digest.py` → 점수순 다이제스트 출력.
- Phase 2: `notify.py` 실행 시 텔레그램에 다이제스트 도착.
- Phase 3: Actions 수동 트리거(workflow_dispatch)로 전체 파이프라인 1회 성공 → 매일 cron 등록.
- 잘못된 `신호유형`/`티어` → enum 검증 거부.

## 12. 정직한 한계 / 범위 밖
- 무료티어는 **일일 호출 한도**, 스크래퍼는 **잘 깨짐**(ToS·구조변경), 무료 LLM은 **뉘앙스 약함** → **좁게 시작·품질 우선·점진 확장.**
- 정밀 컨센서스 리비전 시계열(유료)은 없음 → watchlist는 수동 보완.
- 범위 밖: 유료 구독·복잡한 대시보드·풀 TA·기관급 데이터.
- 생존자 편향 인지: 스코어 높아도 안 오를 수 있음 → 넓은 깔때기 + 종료조건 규율로 대응.

## 13. 역제안/개선은 `IDEAS.md`에 누적 (완벽한 설계 없음 — 계속 진화)
