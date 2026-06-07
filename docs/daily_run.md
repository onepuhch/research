# Claude Daily Discovery Routine

이 문서는 Claude routine이 매일 저장소 루트에서 그대로 실행하는 self-contained 절차다. 목표는 공개 소스를 수집하고, 각 항목을 동일한 루브릭으로 판정해 `signal_log`에 append한 뒤, 새 A/B 신호를 Telegram으로 보내고 중복 방지 상태를 Git에 영속화하는 것이다.

## 0. 실행 전 규칙

0. **실행 환경은 Anthropic 클라우드(Linux)다.** 모든 명령은 POSIX 셸(bash) 기준이며 경로 구분자는 `/`를 쓴다. `python`이 없으면 `python3`를 사용한다.
1. 작업 디렉터리는 `investment-research-system` 저장소 루트여야 한다.
2. 표준 라이브러리 스크립트만 실행한다. 패키지 설치를 하지 않는다.
3. `.env`, API 키, Telegram 토큰을 읽어서 출력하거나 Git에 추가하지 않는다. Telegram 자격증명은 실행 환경의 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`를 사용한다.
4. 아래 파일을 먼저 읽는다.
   - `config/schema.json`: 테이블 컬럼과 enum의 단일 진실원천
   - `PRINCIPLES.md`: 단계 판정 숫자 루브릭
   - `AGENTS.md`: 발굴 원칙과 코드/역할 규칙
5. `signal_log`의 컬럼이나 enum을 추측하지 않는다. 이 문서와 스키마가 다르면 `config/schema.json`을 따른다.
6. 레딧 격리 데이터인 `data/processed/reddit_watch.csv`는 읽거나 `signal_log`로 자동 승격하지 않는다.

## 1. 공개 소스 수집

다음 명령을 실행한다.

```bash
python scripts/collect.py
```

성공 조건:

- exit code가 `0`이다.
- `data/raw/discovery/latest.json`이 생성 또는 갱신된다.
- JSON 최상위 `items`가 배열이다.

실패하면 이후 append와 알림을 실행하지 말고 오류를 보고한다. 수집기가 공개 소스 대신 자체 fallback 항목을 만든 경우에는 그 사실을 결과에 명시하되 나머지 절차는 계속한다.

## 2. `latest.json` 항목 추출

`data/raw/discovery/latest.json`의 `items`를 순서대로 읽는다. 각 항목마다 아래 필드를 만든다. 판단 근거는 해당 항목의 `title`, `raw_text`, `source_type`, `source_name`, `url`로 제한하며, 없는 사실을 만들지 않는다.

### 2.1 필드 계약

| 필드 | 작성 규칙 |
| --- | --- |
| `종목/티커` | 실제 회사명이나 티커가 명시된 경우만 작성한다. 기사 제목, 언론사명, 일반 테마는 종목으로 쓰지 않는다. 확인할 수 없으면 `미분류`. |
| `테마` | 신호가 속한 밸류체인 또는 산업 테마. 판단 불가 시 `미분류`. |
| `신호유형` | `config/schema.json`의 `enums.신호유형` 중 정확히 하나. |
| `특이값 요약` | `무슨 일: ... ｜ 왜 중요: ... ｜ 볼 것: ...` 형식. 사실, 투자 의미, 확인 지표를 각각 한 문장으로 작성한다. |
| `upside_score` | 아래 6축 점수의 합계. 정수 `0`~`12`. |
| `티어` | 합계와 품질 가드를 적용해 `A`, `B`, `관망` 중 하나. |
| `단계 추정` | `관찰`, `초기`, `초기후반`, `중기`, `후기`, `제외` 중 하나. |
| `용어 풀이` | 초보자가 이해하기 어려운 용어 1~2개를 쉬운 한국어로 풀이. 없으면 빈 문자열. |
| `출처` | 원본 항목의 `source_name`. |
| `출처URL` | 원본 항목의 `url`. |

`signal_id`는 작성하지 않는다. `날짜`도 생략한다. `add_entry.py`가 `signal_id`와 오늘 날짜를 생성한다.

### 2.2 신호유형 enum

실행 시 반드시 `config/schema.json`을 다시 확인한다. 현재 분류 의미는 다음과 같다.

- `가이던스상향`: 회사가 매출, 이익, EPS 등 전망을 상향
- `수주/백로그`: 신규 수주, 주문 잔고, 장기 공급계약, 선급금
- `신규고객`: 디자인윈, 신규 고객 채택
- `CAPEX`: 설비투자, 생산능력 증설
- `ASP/가격`: 평균판매단가 또는 가격 인상
- `리드타임`: 납기 증가, sold out, 공급 부족
- `EPS상향`: forward EPS 또는 컨센서스 상향
- `기술로드맵`: 800G, 1.6T, CPO 등 기술 전환과 병목 이동
- `공시(8-K)`: SEC 8-K 공시 자체가 핵심 신호
- `커뮤니티`: 커뮤니티에서 포착된 신호. 단, 격리된 Reddit watch 파일은 자동 입력 금지
- `기타`: 위 enum으로 분류할 수 없는 경우

### 2.3 upside 6축 점수

각 축을 `0`, `1`, `2` 중 하나로 평가하고 합산한다. 근거가 없으면 `0`, 일부 근거면 `1`, 항목 안에 명확한 근거가 있으면 `2`다.

1. `작은 베이스`: 시가총액/유통 규모가 작거나 소외된 순수 플레이어인가.
2. `이익 변곡`: 매출 가속, 매출총이익률 확대, incremental margin, 낮은 EPS 베이스 등 이익 레버리지가 있는가.
3. `공급제약 가격결정력`: ASP 상승, 백로그, 리드타임 증가, sold out 등 수요가 공급보다 강한가.
4. `구조적 수요 드라이버`: AI 등 다년 구조적 수요에 직접 노출되는가.
5. `리비전 초기`: forward EPS 상향이 막 시작됐고 주가 반영이나 분석 커버리지가 낮은가.
6. `재평가 촉매`: 가이던스 상향, 대형 고객, 증설, 신규 커버리지처럼 재평가 계기가 있는가.

합계와 티어:

- `A`: `10`~`12`
- `B`: `6`~`9`
- `관망`: `0`~`5`

품질 가드는 점수보다 우선한다.

- 메가캡 또는 이미 널리 알려진 대형주는 `작은 베이스=0`, 티어 최대 `B`다. 예: NVDA, GOOGL/GOOG, MSFT, AMZN, AAPL, META, TSLA, AVGO, AMD, TSM, MU, ASML, ORCL.
- `종목/티커`가 `미분류` 또는 빈 문자열이면 티어 최대 `B`다.
- 점수는 기사 분위기가 아니라 항목 안의 확인 가능한 근거로만 준다.

### 2.4 단계 판정

`PRINCIPLES.md`의 숫자 기준을 적용한다.

- `관찰`: 가설만 있고 선행지표 추세 전환과 EPS 리비전이 확인되지 않음
- `초기`: 선행지표 1개 방향 전환, EPS 상향 0~1회
- `초기후반`: 선행지표 2개 이상 개선 + 최근 1~2개월 EPS 컨센서스 상향 개시
- `중기`: EPS 상향 2~3개월 연속 및 폭 확대, 선행지표 견조, 동일 기간 EPS 상향률이 주가 상승률 이상
- `후기`: EPS 상향 폭 또는 선행지표 상승률 둔화, 주가 상승률이 EPS 상향률을 초과
- `제외`: EPS 하향 전환, 선행지표 하락 전환, 정량 종료조건 충족

단일 뉴스에 연속성 근거가 없으면 `중기` 이상을 추정하지 않는다. 불확실하면 더 이른 단계로 둔다.

### 2.5 요약 작성

반드시 다음 한 문자열 형식을 사용한다.

```text
무슨 일: 회사가 데이터센터 전력장비 생산능력을 30% 증설한다고 발표했다. ｜ 왜 중요: 전력 병목이 이어질 경우 증설 물량이 매출과 이익 증가로 연결될 수 있다. ｜ 볼 것: 분기 백로그, 신규 설비 가동률
```

- `무슨 일`: 원문에서 확인되는 사실 한 문장
- `왜 중요`: 병목, 직접 수혜, 이익 레버리지, 저평가 가능성을 초보도 이해할 수 있게 한 문장
- `볼 것`: 다음에 확인할 정량/정성 지표 1~2개
- 세 조각 중 근거 없는 조각은 꾸며내지 말고 생략한다. 남은 조각은 ` ｜ `로 연결한다.

## 3. `signal_log` append JSON 작성

추출한 모든 항목을 `data/raw/discovery/daily_signals.json`에 UTF-8 JSON 배열로 저장한다. 각 배열 원소는 다음 형식이다.

```json
[
  {
    "target_table": "signal_log",
    "data": {
      "종목/티커": "EXM",
      "테마": "AI 전력 인프라",
      "신호유형": "CAPEX",
      "특이값 요약": "무슨 일: EXM이 생산능력 30% 증설을 발표했다. ｜ 왜 중요: 전력장비 공급 병목의 직접 수혜가 매출로 전환될 수 있다. ｜ 볼 것: 분기 백로그, 신규 설비 가동률",
      "upside_score": "7",
      "티어": "B",
      "단계 추정": "초기",
      "용어 풀이": "백로그: 아직 매출로 인식되지 않은 주문 잔고.",
      "출처": "SEC EDGAR",
      "출처URL": "https://example.com/source"
    }
  }
]
```

저장 전 확인:

1. 필드명이 `config/schema.json`의 `signal_log.columns`에 존재한다.
2. `신호유형`과 `티어`가 스키마 enum에 존재한다.
3. `upside_score`가 6축 합계와 일치한다.
4. 메가캡/미분류 티어 가드를 적용했다.
5. 출처와 URL이 원본 항목과 일치한다.

append:

```bash
python scripts/add_entry.py data/raw/discovery/daily_signals.json
```

`add_entry.py`는 `signal_log`가 `type: log`인 것을 스키마에서 읽어 각 레코드에 새 `signal_id`를 부여하고 UTF-8-SIG CSV에 append한다. 명령이 하나라도 실패하면 알림과 Git commit을 진행하지 말고 오류를 보고한다.

## 4. Telegram 알림

```bash
python scripts/notify.py
```

동작 규칙:

- 오늘 날짜의 이름이 있는 A/B 신호만 전송한다.
- `data/processed/notify_state.json`의 `pushed` ID는 다시 전송하지 않는다.
- 성공한 전송의 ID만 상태 파일에 저장한다.
- 토큰이 없으면 스크립트는 경고 후 exit `0`으로 끝나며 상태 파일을 변경하지 않는다. 이 경우 알림이 생략됐다고 보고한다.
- `--all`은 일상 루틴에서 사용하지 않는다.

## 5. 상태와 로그 Git 영속화

알림 명령이 끝난 뒤 다음 두 파일만 이 단계에서 stage한다.

```bash
git add data/processed/signal_log.csv data/processed/notify_state.json
git diff --cached --check
git diff --cached --name-only
```

`git diff --cached --name-only` 결과에 `.env`, 키 파일, `data/raw/discovery/` 파일이 있으면 commit하지 말고 즉시 stage에서 제거한다.

commit 후 **반드시 main에 push**한다(클라우드 클론은 휘발성이라 push하지 않으면 누적되지 않는다). 이 routine은 `main`에 직접 push할 수 있도록 "Allow unrestricted branch pushes"가 켜져 있어야 한다.

```bash
git commit -m "chore: daily discovery run YYYY-MM-DD"
git push origin HEAD:main
```

`YYYY-MM-DD`는 실행 날짜로 바꾼다. commit할 변경이 없으면 오류로 취급하지 않고 `no daily data changes`라고 보고한다(이때는 push도 생략).

## 6. 최종 보고

루틴 종료 시 다음을 짧게 보고한다.

- 수집 항목 수와 수집 오류/fallback 여부
- `signal_log` append 건수 및 생성된 `signal_id` 범위
- A/B/관망 건수
- Telegram 전송 건수 또는 생략/실패 사유
- commit hash 또는 변경 없음
- 불확실해서 낮은 단계/점수를 준 항목

어떤 단계에서도 `.env` 내용, API 키, Telegram 토큰 또는 chat ID를 출력하지 않는다.
