# C 보완·D1~D3 구현 인수인계 — 2026-09-25 (Claude)

대상 지시: [D 상세 지시서](d_candidate_delivery_spec_2026-09-25.md). 순서대로 C 보완 → D1 → D2 → D3를 각각 독립 커밋·테스트로 구현했고, 운영(GitHub Actions)에서 실행해 확인했다.

## 커밋과 테스트

| 작업 | 커밋 | 주요 파일 |
|---|---|---|
| C 보완 | f507fd6 | scripts/daily_run_state.py, research_journal.py(--capture-only/--render-only), workflow |
| D1 후보 카드·조회 | a4d4e21 | scripts/candidates.py(신규), templates/candidates.html(신규), telegram_cmd.py, common.py(모델 예산), extract.py, screen_revisions.py(거래소 기록), gen_report.py |
| D2 추적 등록·수집 연결 | 076dd68 | promote.py(promote_candidate), schema.json(origin_candidate_ids), migrate_v2.py(컬럼 변경 전 백업), collect_eps.py(대상 조회) |
| D3 하루 3개 공유 알림 | 029607d | scripts/candidate_alerts.py(신규), notify.py(Delivery 결과 타입·위험 알림 전용) |

테스트 123개 → 192개, 모두 통과(로컬 Windows, CI Ubuntu). 새 테스트가 실제로 버그를 잡는지 코드를 일부러 망가뜨려 확인했다: C 6가지, D2 7가지, D3 9가지 모두 검출.

## 운영 증거

- run 36132330310(auto, C 배포 직후): 기록상 새 단계인 baseline(not_run)과 입력이 바뀐 returns·views만 실행, 나머지 건너뜀. 직후 계획 빈 목록.
- run 36133507734(auto, `redo=screen`): 스크리너 재실행(14분, success) → cards 30초 → views. 카드 30개 모두 SEC 거래소 기반 ID(`NASDAQ:AMCX` 등), 한국어 설명 29/30(AGL 1개는 검증 규칙에 걸려 거부 → "회사 설명 확인 중"), Gemini 3회 호출이 model_budget.json에 기록.
- run 36135589301(auto, D2·D3 배포 후): 추적 입력이 새로 생긴 eps·quarterly·prices(inputs_changed), alerts(not_run), views만 실행. 원장 마이그레이션: `data/archive/pre_columns/investment_review_log_13c5d2de774f.csv`에 기존 파일 보관 후 origin_candidate_ids 컬럼 추가. 기존 활성 아이디어 IDEA-0002~0004(CRDO·ALAB·MRVL) 변화 없음. 직후 계획 빈 목록.
- **실제 전송**: 같은 run에서 첫 도입(bootstrap) 스크린 후보 1개(AMCX, `CAN-14C6F602D0868FB9`)를 텔레그램으로 발송. 영수증: `candidate_alerts.json` 상태 sent, message_id 137, 2026-09-25T12:33:32Z. 나머지 현재 후보 29개는 초기 관측 목록으로 저장. 오늘 뉴스 후보 발송 기록은 없었다(남은 칸 3).

## 운영에서 아직 확인하지 못한 것 (테스트로만 확인)

- 사용자의 실제 `/track CAN-…` 선택과 그 뒤 같은 날 새 종목 수집. 사용자 선택이 없어 임의로 등록하지 않았다.
- 발송 실패(failed) 재시도, 응답 유실(uncertain), 예약 후 중단(reserved) 경로.
- 스크린 실패 후 이전 카드 stale 표시와 알림 중단, partial 결과의 60분 뒤 1회 보완.
- 사람이 승인한 추적 추천(recommended) 흐름. 아직 근거·승인 기록이 없다.
- 새 래퍼 아래 월요일 주간 단계(첫 월요일 9/28).
- 카드 HTML 화면: 로컬 Chrome(데스크톱 1280px·모바일 390px)에서 테스트 복사본(거래소를 가짜로 채운 사본)으로 렌더·필터·가로 넘침 0·스크립트 오류 0을 확인했다. 운영 HTML은 Actions artifact(reports/generated)에만 있고 저장소에는 docs/candidates.md가 저장된다.

## 지시서와 다르게 판단한 점 (Codex 검토 요청)

1. **후보 버전에서 뺀 값**: 매일 움직이는 90일 주가 구간(시작·종료일, 주가 변화, PER 참고 변화), 순위, 관측 시각은 버전 해시에 넣지 않았다. 넣으면 30개 카드가 매일 새 버전이 된다. EPS 수치·대상 기간·목록 충족·분류 입력·설명·출처는 들어간다. 주가 비교는 최신 목록(index)에 관측값으로만 붙는다.
2. **카드 범위**: 스크린 통과 전체(오늘 101개)가 아니라 A·B 상위 목록 합집합(최대 40, 오늘 30)만 카드로 만든다. 나머지는 docs/revision_screen.md에 남는다.
3. **needs_evidence 기준**: 카드 필수 자료(식별, 주가 비교, 업종)가 빠진 경우로 정했다. 사람이 "보강 필요"로 지정하는 흐름은 없다.
4. **추천 근거·승인 저장**: `data/processed/candidate_evidence.json`에 다섯 설명과 출처를 넣고 `python scripts/candidates.py approve CAN-… --by 이름`으로 현재 버전을 승인한다. 텔레그램에서는 승인하지 않는다.
5. **번역**: Gemini 한 번에 10개씩, cards 실행당 최대 3회. 원문에 없는 숫자가 들어가거나 한글이 없으면 거부한다.
6. **모델 예산**: extract의 max_model_calls가 실행당에서 KST 하루 전체(모든 구성요소 합계)로 바뀌었다. 오늘 배포 전 extract 호출은 기록되지 않았다.
7. **추가 기능**: workflow_dispatch 입력 `redo`(auto 전용, 예: screen). 지정 단계와 그 결과를 쓰는 단계만 다시 돈다. 오늘 운영 검증에 사용했다.
8. **blocked 단계 종료 코드**: 0으로 끝내고 경고만 남긴다. 실패한 선행 단계가 이미 job을 실패로 표시하기 때문이다.
9. **알림 형식**: 알림 1건 = 메시지 1개로 보내 message_id를 이벤트마다 남긴다. 텔레그램 4xx·연결 실패는 failed, 시간 초과·5xx·읽을 수 없는 응답은 uncertain.
10. **채널 간 중복**: 뉴스 가설 키(병목 ID·테마)와 스크린 가설 키(eps-revision-review:v1)가 달라서 "같은 기업+가설" 규칙은 실제로 거의 맞지 않는다. 실효 규칙은 "같은 날 같은 기업 한 번"이다. 다른 날에는 같은 기업이 뉴스와 스크린으로 한 번씩 알림될 수 있다. 막아야 하면 기업 단위 기간 규칙을 정해 달라.
11. **첫 도입 개수**: 지시서의 "최대 3개" 안에서 "실발송은 1개로 먼저 검증"을 따라 policy candidate_alerts.bootstrap_max=1로 뒀다. 첫 도입은 이미 끝나서 이 값은 더 쓰이지 않는다.
12. **추적 상태 판정**: 같은 기업의 활성 아이디어가 가설과 무관하게 하나라도 있으면 카드에 "추적 중"으로 표시하고 `/history` 명령을 준다.
13. **최신 목록에서 빠진 후보의 /track**: 관측이 signal_lookback_days(14일) 이내면 등록을 허용하고 답변에 "최신 목록에는 없는 후보"라고 표시한다.
14. **ID 문법**: 직접 경로는 지시대로 `CAN-`(대문자)+16진수만 허용한다. 텔레그램 큐는 인자를 대문자로 바꾸므로 사용자가 소문자로 입력해도 된다. `/track CAN`(티커 CAN)은 ID가 아니라 기존 티커 경로다.
15. **신규 추적 티커의 수집 메타데이터**: entities.json을 자동으로 고치지 않는다. 후보 버전이 검증한 거래소·통화를 수집 시 조회한다.

## 다음 할 일 제안

- 사용자가 실제로 `/track CAN-…`를 한 뒤 다음 auto에서 해당 티커의 EPS·분기·가격 첫 관측이 생기는지 확인.
- 9/28 월요일 주간 단계 확인.
- 위 1·10·11 결정.
- 종목별 대시보드 페이지(GitHub Pages)와 업계 가격·공급 신호는 이번 범위 밖으로 남겼다.

## 부록: 카드 예시

### 1. 정상 (운영 카드, 2026-09-25 12:25 UTC 관측)

#### 발굴 후보 · AMCX AMC Global Media Inc.
CAN-14C6F602D0868FB9 · Entertainment · 미추적

**무엇으로 돈을 버나**

AMC, We TV 등 방송 네트워크를 운영하고 스트리밍 서비스 제공 및 오리지널 콘텐츠 제작, 배급으로 수익을 얻습니다.

**후보가 된 이유**

- A 1위: 이익수익률 변화 +10.57%p (내년 EPS 예상 증가분 ÷ 현재 주가, 기준 1.0%p 이상)
- B 12위: 내년 EPS 예상 90일 변화 +86% (기준 +25% 이상, 90일 전 EPS $0.25 이상)
- 최근 30일 추정 상향 7 / 하향 0, 분석가 7명

**숫자 (관측 2026-09-25 12:24 UTC)**

- 내년 EPS 예상 (2027-12-31 회계연도 말, USD, Yahoo Finance earningsTrend (+1y), 회계기준 미표시): 90일 전 $1.48 → 30일 전 $2.54 → 현재 $2.76 (+86%)
- 주가 2026-06-26 → 2026-09-24: +19.3% (분할 조정 종가, 배당 미조정) · 같은 기간 PER 참고 변화 -36% (저평가 입증 아님)

**확인된 사업 근거**

아직 없음. EPS 예상 상향이 왜 생겼는지 원문으로 확인하지 않았습니다.

**미확인 · 반증**

- 스크린 조건 기준 반증: 다음 관측에서 내년 EPS 예상이 30일 전보다 낮아지거나 30일 하향 수가 상향 수 이상이면 후보 조건이 깨집니다.
- 시장이 이 상향을 반영하지 않았는지는 확인되지 않았습니다. PER 변화는 참고 지표입니다.

**다음 확인**

- 최근 실적 발표·가이던스 원문에서 이익 증가 원인과 지속 기간 확인

**출처**

- [AMCX analyst estimates (EPS trend)](https://finance.yahoo.com/quote/AMCX/analysis) (관측 2026-09-25)
- [AMCX daily closes](https://finance.yahoo.com/quote/AMCX/history) (관측 2026-09-25)
- [AMCX company profile](https://finance.yahoo.com/quote/AMCX/profile) (관측 2026-09-25)

텔레그램: `/track CAN-14C6F602D0868FB9`

### 2. 자료 부족 (테스트 입력: 90일 전 종가 없음·프로필 설명 없음)

#### 발굴 후보 · 자료 보강 필요 · AAA AAA Inc.
CAN-05D6842AF46DC2C6 · Semiconductors · 미추적

**무엇으로 돈을 버나**

회사 설명 확인 중 (AAA)

**후보가 된 이유**

- A 1위: 이익수익률 변화 +2.00%p (내년 EPS 예상 증가분 ÷ 현재 주가, 기준 1.0%p 이상)
- 최근 30일 추정 상향 4 / 하향 0, 분석가 5명, 30일·90일 모두 상향

**숫자 (관측 2026-09-25 01:15 UTC)**

- 내년 EPS 예상 (2027-12-31 회계연도 말, USD, Yahoo Finance earningsTrend (+1y), 회계기준 미표시): 90일 전 $1.00 → 30일 전 $1.50 → 현재 $2.00 (+100%)
- 주가 비교 미확보: 90일 전 종가 없음(거래 기간 부족)

**확인된 사업 근거**

아직 없음. EPS 예상 상향이 왜 생겼는지 원문으로 확인하지 않았습니다.

**미확인 · 반증**

- 자료 부족: price_comparison (90일 전 종가 없음(거래 기간 부족))
- 스크린 조건 기준 반증: 다음 관측에서 내년 EPS 예상이 30일 전보다 낮아지거나 30일 하향 수가 상향 수 이상이면 후보 조건이 깨집니다.
- 시장이 이 상향을 반영하지 않았는지는 확인되지 않았습니다. PER 변화는 참고 지표입니다.

**다음 확인**

- 최근 실적 발표·가이던스 원문에서 이익 증가 원인과 지속 기간 확인

**출처**

- [AAA analyst estimates (EPS trend)](https://finance.yahoo.com/quote/AAA/analysis) (관측 2026-09-25)
- [AAA daily closes](https://finance.yahoo.com/quote/AAA/history) (관측 2026-09-25)

텔레그램: `/track CAN-05D6842AF46DC2C6`

### 3. 추적 중 (테스트 입력: CRDO가 활성 아이디어로 등록된 경우)

#### 발굴 후보 · CRDO CRDO Inc.
CAN-AA0B9C2988C4796B · Semiconductors · 추적 중 (IDEA-0002)

**무엇으로 돈을 버나**

회사 설명 확인 중 (CRDO)

**후보가 된 이유**

- A 2위: 이익수익률 변화 +2.00%p (내년 EPS 예상 증가분 ÷ 현재 주가, 기준 1.0%p 이상)
- 최근 30일 추정 상향 4 / 하향 0, 분석가 5명, 30일·90일 모두 상향

**숫자 (관측 2026-09-25 01:15 UTC)**

- 내년 EPS 예상 (2027-12-31 회계연도 말, USD, Yahoo Finance earningsTrend (+1y), 회계기준 미표시): 90일 전 $1.00 → 30일 전 $1.50 → 현재 $2.00 (+100%)
- 주가 2026-06-26 → 2026-09-24: +10.0% (분할 조정 종가, 배당 미조정) · 같은 기간 PER 참고 변화 -45% (저평가 입증 아님)

**확인된 사업 근거**

아직 없음. EPS 예상 상향이 왜 생겼는지 원문으로 확인하지 않았습니다.

**미확인 · 반증**

- 스크린 조건 기준 반증: 다음 관측에서 내년 EPS 예상이 30일 전보다 낮아지거나 30일 하향 수가 상향 수 이상이면 후보 조건이 깨집니다.
- 시장이 이 상향을 반영하지 않았는지는 확인되지 않았습니다. PER 변화는 참고 지표입니다.

**다음 확인**

- 최근 실적 발표·가이던스 원문에서 이익 증가 원인과 지속 기간 확인

**출처**

- [CRDO analyst estimates (EPS trend)](https://finance.yahoo.com/quote/CRDO/analysis) (관측 2026-09-25)
- [CRDO daily closes](https://finance.yahoo.com/quote/CRDO/history) (관측 2026-09-25)
- [CRDO company profile](https://finance.yahoo.com/quote/CRDO/profile) (관측 2026-09-25)

텔레그램: `/history CRDO`
