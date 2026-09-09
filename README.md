# 투자리서치 시스템

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

GitHub Secrets 또는 로컬 .env: GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. 기본 Yahoo EPS 수집에는 키가 필요 없다. FMP_API_KEY는 eps_provider를 fmp로 선택할 때만 필요하다. SEC_USER_AGENT는 실제 운영자 연락처가 포함된 식별 문자열로 설정하고 GitHub에서는 Repository Variable을 사용한다. 키 값과 .env는 커밋하지 않는다.

EPS 공급자는 config/research_policy.json의 eps_provider로 선택한다. 기본 yahoo는 공개 페이지의 명시적인 non-GAAP 연간 컨센서스만 수집하며, 회사·통화·기간·분석가 수를 검사한다. 공급자별 시계열을 합치지 않는다. FMP는 현재 키로 HTTP 402이므로 기본 운영에서 호출하지 않는다. EPS 결측을 회사 실적이나 가이던스로 채우지 않는다.

새 workflow 설정은 KST 매일 09:17 수집·추출·EPS·알림, 03:23/09:23/15:23/21:23 명령 처리다. 주간 검토 보고는 월요일이다. GitHub 스케줄은 정확한 시각을 보장하지 않는다. /track은 최근 14일 신호를 지원하고 재실행 시 기존 아이디어를 반환한다. 명령 큐를 먼저 저장한 뒤 offset을 갱신해 응답 실패를 재시도한다.

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
