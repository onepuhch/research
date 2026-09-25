# 투자리서치 시스템

누적 데이터: [날짜별 관측 원장](docs/data_history.md) · [저장·운영·웹 구조 점검](docs/architecture_review_2026-09-25.md).
Telegram에서 `/data`, `/history CRDO`로 조회한다. 명령은 약 6시간 간격 예약 처리이며 즉시 응답을 보장하지 않는다.
`python scripts/data_history.py --save`는 누적 문서와 `reports/generated/data_history.html` 조회 화면을 생성한다.
HTML은 로컬 또는 Actions artifact에서 내려받는 생성 시점 스냅샷이다. 새 도메인·상시 웹 서버는 아직 운영하지 않는다.
일간 `collect_quarterly.py`는 현재·다음 분기 EPS/매출을 관측하고, `run_history`는 각 실제 실행 상태를 보존한다.
일간 `screen_revisions.py`는 미국 상장사(시가총액 3억 달러·분석가 3명 이상, 약 3,300개)의 내년 EPS 예상치 90일 변화를 Yahoo에서 받아 두 기준(이익 규모 대비·성장률)으로 순위를 매기고 `docs/revision_screen.md`에 쓴다. 요청 간격·재시도·시간 예산은 `research_policy.json`의 revision_screen이 정한다. 단계(상장 목록·접속·시세·EPS·업종·주가)마다 종목을 정상/자료 부족/실패/미시도로 집계하고, 실패·미시도가 있으면 degraded, 핵심 입력이 없으면 failed(종료 코드 1)로 기록한다. 실행마다 `data/processed/revision_screen/{UTC시각}_{run_id}.json.gz`에 설정·코드 버전·단계 결과·재채점용 원자료를 남긴다. 최신 시도가 실패하면 문서는 이전 결과를 이전 시각으로 표시한다. Yahoo가 제공한 7/30/60/90일 전 값은 스크리닝에만 쓰고 metric_log 관측으로 넣지 않는다. `--tickers A,B`는 저장 없이 소수 종목의 접근과 필드를 확인한다. max_attempts는 한 패스 기준이라 실패 종목은 30초 뒤 재조회까지 최대 2×max_attempts회 요청하며, 전체 time_budget_s가 우선한다. 업종이 빈 응답, 비교할 수 없는 주가 응답은 성공으로 세지 않는다. 주가 비교는 NYSE 달력(`market_calendar.py`, 성과 복기와 공용)으로 마감 1시간이 지난 거래일 종가만 쓰고, 종료점이 기대 거래일보다 1거래일 넘게 오래됐거나 시작점이 90일 기준일보다 7일 넘게 이르면 미산출(자료 부족)로 둔다.

일간 `candidates.py generate`(cards 단계)는 스크리너의 A·B 상위 목록을 번갈아 놓은 순서(A1·B1·A2…, 기업당 1회, 투자 점수 아님)로 후보 카드를 만든다. 후보 ID는 `CAN-`+SHA256(기업 식별자|가설 키) 앞 16자리이며, 기업 식별자는 entities.json 등록값, 없으면 SEC 목록의 거래소:티커다(CIK 추측 없음, 거래소를 모르면 ID·추적 명령 없이 표시). 가설 키는 `eps-revision-review:v1`(EPS 상향의 사업 원인과 지속성 검토). 후보 버전은 카드 주장(식별·EPS 수치·대상 기간·목록 충족·분류 입력·설명·출처)의 해시로, 수집 시각·순위·매일 움직이는 주가 구간은 버전을 바꾸지 않는다. 버전은 `data/processed/candidate_history/{버전}.json`에 한 번만 저장되고, 최신 목록 `candidates/index.json`은 재생성 가능하다. 분류(발굴 후보 found / 자료 보강 필요 needs_evidence / 추적 추천 recommended)와 추적 상태(미추적/추적 중/종료, 원장 기준)는 따로 둔다. 추적 추천은 `candidate_evidence.json`에 다섯 설명(이익 경로·지속 근거·시장 기대와의 차이·반증·다음 점검)이 모두 출처와 연결되고 `candidates.py approve CAN-… --by 이름`으로 사람이 현재 버전을 승인한 경우에만 붙으며, 내용이 바뀌면 재검토 표시로 돌아간다. 회사 한 줄 설명은 Yahoo 프로필을 Gemini로 한국어 번역한 것(원문 해시 캐시, 원문에 없는 숫자가 있으면 거부)이고, 모델 호출은 extract와 하루 예산(max_model_calls)을 공유한다(`model_budget.json`). 최신 스크린 시도가 실패하면 이전 유효 카드에 마지막 유효 관측일과 실패를 표시한다. 결과는 `docs/candidates.md`, 필터·상세 카드 화면 `reports/generated/candidates.html`, 텔레그램 `/screen`(상위 5개)·`/candidate CAN-…`(카드 상세)로 본다. 수동 실행에서 `redo=screen`처럼 적으면(auto 전용) 그 단계와 결과를 쓰는 단계만 오늘 다시 돈다. 텔레그램 `/track CAN-…`는 사용자의 추적 선택을 `promote.promote_candidate`로 원장에 등록한다(뉴스 SIG를 만들지 않음, `origin_candidate_ids` 컬럼에 후보 ID). 같은 기업+가설의 활성 아이디어가 있으면 그 idea_id를 돌려주고 후보 연결만 한 번 기록한다. 새 등록은 관찰·사업 단계 미확인·근거 수준 가설·검토 상태 추적(사용자 선택이며 검증 승격 아님)·사이클 리비전형이며, 등록 당시 후보 버전·원자료·기준 숫자·미확인 항목을 행과 review_history에 남긴다. 활성 아이디어 상한·관측 기한(signal_lookback_days)·식별/통화 확인이 부족하면 쓰기 전에 거절한다. 등록 직후 수집은 하지 않고, 추적 원장 변화가 eps·quarterly·prices·cards의 입력이라 다음 auto 실행에서 새 종목이 수집 대상에 들어간다. entities.json에 없는 티커는 후보 버전이 검증한 거래소·통화로 수집한다. 원장 컬럼이 바뀌면 migrate_v2가 기존 파일을 `data/archive/pre_columns/`에 먼저 보관한다.

신규 후보 알림은 `candidate_alerts.py`(alerts 단계, cards 성공이 필수, extract가 다시 끝나면 재실행)가 보낸다. 뉴스 A/B 신호와 스크린 후보가 KST 하루 한도(daily_candidate_limit=3)를 함께 쓰며, notify.py가 오늘 이미 보낸 뉴스 후보도 한도에 센다. 순서는 사람이 승인한 추적 추천 → 뉴스·스크린 교대(날짜마다 첫 채널 교대, 빈 채널의 칸은 다른 채널이 사용)이며 발송 칸 배분일 뿐 투자 점수가 아니다. 같은 기업|가설|이벤트는 한 번만 알린다(순위·수집일·회계연도 이동으로 재알림 없음). 같은 기업은 하루 한 번만 알리고, 다른 가설·채널의 새 발견은 그 기업의 마지막 새 발견 알림 뒤 14일(entity_new_cooldown_days)이 지나야 알린다. 사람이 승인한 추적 추천 알림은 승인 버전마다 한 번이며 14일 간격의 예외다(하루 한 번·전체 3개 제한은 적용). 기업 비교는 entities.json의 확정 매핑(CIK와 거래소:티커)으로만 합치고 이름 유사성으로 합치지 않는다. 뉴스 후보는 적격 신호 전체에서 중복을 거른 뒤 한도를 적용한다. notify.py가 예전에 보낸 뉴스 후보도 신호 원장으로 기업을 찾아 같은 규칙에 반영하고, 찾지 못한 건수는 unknown으로 남긴다. 스크린 후보는 최신 수집이 완전(success, stale 아님)하고 카드 자료가 모두 있을 때만 알린다. 발송 원장 `candidate_alerts.json`은 예약(본문 해시·관측 ID·실행 ID) → 원격 저장(push) → 발송 → 영수증 → 원격 저장 순서로 기록한다. 예약 push가 실패하면 한 건도 보내지 않고 예약을 해제한다. 다른 실행이 남긴 예약(중단·영수증 저장 실패)은 다음 실행이 uncertain으로 격리하고 자동 재발송하지 않는다(중복보다 누락을 택함). sent는 텔레그램이 ok와 올바른 message_id를 준 경우만이며, 연결이 끊겨 전송 여부를 모르면 uncertain, DNS 실패·연결 거부·4xx 거절만 failed(같은 이벤트로 재시도)다. 예약·uncertain도 하루 한도에 포함한다. 실발송은 CI 단일 작성자 작업에서만 하며 로컬 실행은 예약을 원격에 저장하지 않으므로 보내지 않는다. 정확히 한 번 전송은 보장하지 않으며, 주간 보고·명령 응답 경로는 이 보장 범위 밖이다. 원문이 긴 뉴스는 출처와 추적 명령을 남긴 요약본으로 보낸다. 첫 도입일에는 스크린 후보를 bootstrap_max(1)개만 보내고 나머지 현재 후보는 초기 관측 목록으로 저장해 이후 새 발견으로 다시 알리지 않는다. notify.py는 추적 종목 위험 알림만 보내며(카드 실패와 무관), 발송 결과를 sent/failed/uncertain으로 구분해 uncertain도 재발송하지 않는다. `--dry-run`은 발송·원장 쓰기가 없다.

해외 밸류체인 신호를 원문 근거와 함께 모으고, 소수의 가설을 숫자·반증 조건·판단 이력으로 추적한다. 2026-09-07 원격 main 배포와 운영 실행, 실제 Telegram 보고서 전달을 확인했다. 2026-09-09 EPS 기본 공급자를 추가 결제가 필요 없는 Yahoo Finance 공개 컨센서스로 교체했고, 접근이 차단된 Import AI 피드는 수집 설정에서 제외했다. 검증 결과는 STATUS.md를 참조한다.

## 빠른 확인 (PowerShell, Python 3.11 이상)

```powershell
$env:PYTHONIOENCODING = "utf-8"
python -m unittest discover -s tests -v
python scripts/migrate_v2.py
python scripts/gen_report.py board
python scripts/gen_report.py weekly
python scripts/gen_report.py metric CRDO
python scripts/gen_report.py valuation CRDO
python scripts/gen_report.py bottlenecks
python scripts/gen_report.py quality
python scripts/gen_report.py health
python scripts/notify.py --dry-run --report
python scripts/telegram_cmd.py --dry-run --command "/list"
```

Python 패키지 설치는 필요 없다. 생성물은 reports/generated에 저장한다. RESEARCH_DATA_DIR로 처리 원장 경로를 바꿔 격리 검증할 수 있다. 원자료 수집 경로와 보고서 경로는 별도이므로 전체 파이프라인 격리에는 임시 체크아웃을 사용한다.

## 처리 흐름

| 단계 | 실행 | 결과 |
| --- | --- | --- |
| 수집 | collect.py | SEC·RSS 문서와 정확한 문서 URL, 수집 실패 상태 |
| 추출 | extract.py | 원문 인용에 근거한 신호; accepted/rejected/retry/deferred 원장 |
| 검토 등록 | promote.py SIG-ID | 기업+가설 중복 방지, 원신호 연결, 다음 점검일 |
| 숫자 관측 | collect_eps.py / add_entry.py | 동일 정의의 실제 관측값, 컨센서스와 실적 분리 |
| 점검 | gen_report.py | 지표 부족·노후화·반증 조건·판단 변화 |
| 평가 | evaluate.py | 티어별 표본 검토 대기 CSV; 자동 정답 없음 |

API 실패 시 키워드 기반 신호를 생성하지 않는다. 재시도 대상은 원문 스냅샷과 함께 보존한다. 동일 원문이 기각되면 모델을 반복 호출하지 않는다. 추출 호출은 실행당 최대 20회이며 재시도 간격 기본값은 12시간이다. 원문 보관 기간 자동 삭제는 구현하지 않았다.

신규 알림은 live·원문 인용·유효 발표일·계약/실현 사건 조건을 충족하는 A/B 중 하루 최대 3건이다. 추적 기업의 부정 신호는 티어 제한과 별도로 전달한다. 대형 고객 문서는 수요 근거로 보존한다. 단일 문서로 입증할 수 없는 ‘미주목’·‘EPS 리비전’ 점수는 0이므로 자동 A 생성은 의도적으로 제한된다.

## 데이터와 갱신

config/schema.json이 테이블과 enum의 기준이다. data_quality의 live는 검증 출처를 갖춘 운영 자료, legacy는 재검증이 필요한 기존 자료, example은 예제, quarantine은 격리 자료다. live가 미래 수익성을 보증하지 않는다.

```powershell
python scripts/add_entry.py path/to/input.json
python scripts/promote.py SIG-0874 --thesis-key VC-INTERCONNECT --ticker CRDO
python scripts/evaluate.py
```

검토 갱신에는 idea_id와 새 변경 사유를 넣는다. 추적 상태로 전환하려면 출처URL, 모니터링 지표, 종료 조건(정량), 다음 점검일, 추적 지표 정의가 필요하다. 변경 전후는 review_history에 보관된다. 실제 재현 입력은 data/research/crdo_2026-09-06/registration.json을 참고한다. 이 파일은 소급 실적 등록이며 컨센서스 자료가 아니다.

수동 컨센서스 등록은 [운영 절차](docs/daily_run.md)를 따른다. as_of를 과거로 바꾸어 가상의 관측 이력을 만들지 않는다. 시점이 표시된 실제 과거 자료를 확보한 경우에만 소급 관측 근거를 명시한다.

## 외부 연결 및 자동 실행

GitHub Secrets 또는 로컬 .env: GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. 기본 Yahoo EPS 수집에는 키가 필요 없다. FMP_API_KEY는 eps_provider를 fmp로 선택할 때만 필요하다. SEC_USER_AGENT는 실제 운영자 연락처가 포함된 식별 문자열로 설정하고 GitHub에서는 Repository Secret을 사용한다(공개 저장소 로그에 연락처가 찍히지 않도록). 워크플로는 Secret이 없을 때만 Variable을 읽는다. 키 값과 .env는 커밋하지 않는다.

EPS 공급자는 config/research_policy.json의 eps_provider로 선택한다. 기본 yahoo는 공개 페이지의 명시적인 non-GAAP 연간 컨센서스만 수집하며, 회사·통화·기간·분석가 수를 검사한다. 공급자별 시계열을 합치지 않는다. FMP는 현재 키로 HTTP 402이므로 기본 운영에서 호출하지 않는다. EPS 결측을 회사 실적이나 가이던스로 채우지 않는다.

새 workflow 설정은 KST 매일 09:17 수집·추출·EPS·알림, 03:23/09:23/15:23/21:23 명령 처리다. 주간 검토 보고는 월요일이다. GitHub 스케줄은 정확한 시각을 보장하지 않는다. 사용자 PC 타이머가 09:17에 mode=auto, 명령 시각에 mode=commands로 dispatch하고 GitHub 예약은 대체용이다(일간 예약=auto, 6시간 예약=commands).

일간 완료는 `scripts/daily_run_state.py`의 필수 단계로 판단한다. 단계 순서는 수집/계산(collect, extract, eps, notify, quarterly, screen, prices) → baseline(기준 스냅샷 고정) → returns → views → 월요일(KST)에만 community·weekly_report다. 단계 관계는 이 파일 한 곳에서만 정의한다. '필수 선행'(extract←collect, notify←extract, weekly_report←views)은 앞 단계가 이번 계획 기준으로 성공하지 않았으면 명령을 호출하지 않고 blocked(이유·dependency_run_id)로 기록한다. '입력 갱신'(returns←baseline, views←extract·eps·quarterly·screen·prices·baseline·returns)은 입력 단계가 다시 끝나면(성공이든 실패든) 같은 날에도 화면을 다시 만든다. views는 입력 실패로 멈추지 않고 그 실패와 이전 관측 시각을 보여준다. 화면 생성 버전이 바뀌어도 다시 만든다. 각 단계는 실행 상태(pending/started/success/failed/blocked)와 자료 품질(complete/partial/unavailable/unknown)을 따로 `data/processed/daily_runs.json`에 남기며, 결과물과 같은 커밋으로 저장된다. 종료 코드 0은 프로세스가 끝났다는 뜻이고, 스크리너 품질은 이번 실행의 스냅샷(run_id 일치)에서 읽는다(degraded=partial). auto는 오늘 success가 아닌 단계, 입력이 바뀐 화면, 보완 시점이 된 partial 단계와 그것을 쓰는 단계만 실행한다. 계획을 저장할 때 다시 실행할 단계를 모두 pending으로 무효화하므로, 중간에 끊겨도 다음 auto가 남은 단계를 이어간다(이전 성공 시각과 시도 이력은 보존). partial 단계는 KST 하루에 추가 1회, 마지막 시도 60분 뒤 다음 auto 실행에서 보완한다(research_policy.json daily_run). 한도를 다 써도 품질은 partial로 남는다. daily는 모든 단계를 새 run 기록으로 다시 실행한다. commands 실행은 일간 완료로 세지 않는다. push가 거절되면 원격에 success 기록이 없으므로 다음 실행이 다시 시도한다. /track은 최근 14일 신호를 지원하고 재실행 시 기존 아이디어를 반환한다. 명령 큐를 먼저 저장한 뒤 offset을 갱신해 응답 실패를 재시도한다.

외부 서비스별 실패를 분리하고 실패 후에도 상태를 저장한다. scripts/persist_state.py는 깨끗한 CI 체크아웃 전용이며 git commit/push를 수행한다. 로컬 변경 검토용 명령이 아니다. 전달 성공 직후 상태 저장 전 프로세스가 종료되는 경우 Telegram의 정확히 한 번 전송은 보장하지 못한다.

## 보존과 복구

migrate_v2.py는 data/archive/pre_v2에 원본과 SHA-256 manifest를 보관하고 예제를 분리한다. CSV 교체는 원자적으로 수행하며 투자 검토와 이력은 pending_tables.json 저널로 복구한다. 여러 프로세스가 동시에 원장을 쓰지 않도록 운영한다. 손상된 알림 상태는 백업을 복원한 후 재개한다.

Google Sheets 코드는 docs/gas_main.js에 있다. v2 전용 탭을 사용하며 기존 탭을 보존한다. 동일한 기존 컬럼 뒤에 추가된 컬럼만 자동 확장한다. 실제 Sheet ID 설정과 Apps Script 배포는 수행하지 않았다.

## 문서

- [현재 상태](STATUS.md)
- [투자 연구 원칙](PRINCIPLES.md)
- [전체 감사](docs/project_audit_2026-09-06.md)
- [개선 적용 결과](docs/implementation_2026-09-07.md)
- [CRDO 재점검](docs/crdo_review_2026-09-06.md)
- [운영 절차](docs/daily_run.md)

## 실제 가설 연구

`python scripts/gen_report.py cases`로 병목 → 후보 → 시장 기대 차이 → 숫자 → 반증까지 한 화면에서 확인한다. [AI 연결 연구 사례](docs/interconnect_research_2026-09-09.md)는 기준일 스냅샷이고, data/research/cases의 구조화된 가설과 metric_log를 연결해 매일 새 보고서를 만든다. 주간 보고서와 Telegram 주간 보고에도 가설 요약이 포함된다.

현재 연구 우선순위는 ALAB, 비교 대상은 CRDO·MRVL이다. 매매 추천 순위가 아니며 공급 부족·시장 미반영이 입증됐다는 뜻이 아니다. 컨센서스는 자동 관측하고, 제품별 매출·고객 계약·실적 발표의 실제 수치는 원문 확인 후 add_entry로 등록한다. 미래 수치가 없으면 반증 결과는 자료 부족으로 남는다.

### 가격과 시장 기대 재점검

`python scripts/collect_prices.py`는 활성 기업의 Yahoo 정규장 시세를 수집한다. 거래 시각과 수집 시각을 분리하고 기업·통화·시세 노후화를 검증한다. `gen_report.py cases`와 주간 보고서는 같은 EPS 정의별 참고 PER을 표시하며, 다른 시점·회계연도 간 저평가 순위를 만들지 않는다. 가격 수집 실패는 운영 상태판의 prices에 기록한다.

2026-09-14 재점검과 가정별 영업이익 민감도는 [연구 보고서](docs/interconnect_research_2026-09-14.md)에 있다. 원자료·연구 변경 입력·운영 감사는 data/research/interconnect_2026-09-14에 보관한다. ALAB·CRDO 분기 컨센서스와 행사 녹취 미확보를 명시했다.

GitHub 예약 실행에는 지연이 발생할 수 있다. 9월 14일 일간 실행은 명목 시각보다 약 4시간 47분 늦게 시작했다. checkout은 동시 실행 대기 후 최신 브랜치를 읽도록 지정했다. 실행 도중 외부 작성자가 같은 상태를 변경하면 강제 덮어쓰기 대신 저장 실패를 표시한다.

## 판단 스냅샷과 실제 결과 복기

`python scripts/research_journal.py`는 현재 가설 개정을 고정하고 실제 실적과 비교한 outcomes 보고서를 생성합니다(`--capture-only`는 고정만, `--render-only`는 보고서만. 일간 운영은 baseline 단계에서 고정하고 views 단계에서 보고서를 만듭니다). 일간 운영에도 연결되어 있으며 `python scripts/gen_report.py quality`와 텔레그램에 평가 상태가 표시됩니다. 저장소는 `data/processed/research_journal/`입니다. 재실행으로 기준 관측을 바꾸지 않으며 미래 실적이 없으면 대기합니다.

[평가 기준과 후속 연구](docs/research_followup_2026-09-14.md) · [최초 복기 보고서](docs/research_outcomes_2026-09-14.md). 주가 성과 자동 계산은 2026-09-24 구현했습니다. `python scripts/research_returns.py`로 실행합니다.
