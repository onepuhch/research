# investment-research-system

업종, 밸류체인, 병목, 지표 변화, EPS 리비전, 투자 판단 복기를 로컬 CSV로 관리하는 투자 리서치 시스템입니다.

운영 원칙은 [PRINCIPLES.md](PRINCIPLES.md)를 기준으로 합니다. 테이블/컬럼/enum은 [config/schema.json](config/schema.json) 한 곳에서만 정의합니다.

## 폴더 구조

```text
investment-research-system/
├─ README.md
├─ PRINCIPLES.md
├─ AGENTS.md
├─ CLAUDE.md
├─ STATUS.md
├─ config/
│  ├─ schema.json
│  └─ discovery_sources.json
├─ data/
│  ├─ raw/
│  └─ processed/
│     ├─ sectors.csv
│     ├─ industry_indicators.csv
│     ├─ bottleneck_log.csv
│     ├─ investment_review_log.csv
│     ├─ metric_log.csv
│     └─ signal_log.csv
├─ docs/
│  └─ metric_log_design.md
├─ examples/
├─ scripts/
│  ├─ common.py
│  ├─ add_entry.py
│  ├─ export_tsv.py
│  ├─ gen_report.py
│  ├─ collect.py
│  ├─ extract.py
│  ├─ digest.py
│  └─ create_templates.py
└─ reports/
   ├─ templates/
   └─ generated/
```

## 실행 환경

Python 3.9+ 표준 라이브러리만 사용합니다. 외부 패키지, Google Sheets API, 유료 데이터 연동은 아직 사용하지 않습니다.

Windows PowerShell 기준:

```powershell
cd "C:\Users\wls15\OneDrive\바탕 화면\투자리서치\investment-research-system"
```

## JSON 입력

```powershell
python scripts\add_entry.py examples\sector_memory.json
python scripts\add_entry.py examples\industry_indicator_memory.json
python scripts\add_entry.py examples\bottleneck_log_example.json
python scripts\add_entry.py examples\memory_review.json
```

입력 형식:

```json
{
  "target_table": "investment_review_log",
  "data": {
    "종목/업종": "메모리 반도체"
  }
}
```

테이블 동작:

| 테이블 유형 | 동작 |
| --- | --- |
| `master` | key 기준 upsert |
| `log` | ID 자동 부여 후 append |
| `tracked` | ID가 있으면 갱신, 없으면 새 ID 생성 |

CSV는 모두 UTF-8-SIG로 저장합니다.

## Discovery Engine Phase 1

무료 공개 소스에서 원문 후보를 수집하고, 규칙 기반 추출로 `signal_log.csv`에 신호를 누적한 뒤 점수순 다이제스트를 출력합니다. 소스는 [config/discovery_sources.json](config/discovery_sources.json)에서 관리합니다.

```powershell
python scripts\collect.py
python scripts\extract.py
python scripts\digest.py
python scripts\digest.py --top 5
```

- `collect.py`: EDGAR/RSS 원문 후보를 `data\raw\discovery\latest.json`에 저장
- `extract.py`: 수집 원문에서 `신호유형`, `upside_score`, `티어`, `단계 추정`을 추출해 `signal_log.csv`에 append
- `digest.py`: `signal_log.csv`를 `upside_score`와 `티어` 기준으로 정렬해 콘솔과 `reports\generated`에 출력

## metric_log

지표/리비전 시계열을 기록합니다. 같은 FY끼리 비교해야 하므로 지표명에 연도를 포함합니다. 예: `2027F EPS`.

```powershell
python scripts\add_entry.py examples\metric_log_example.json
python scripts\add_entry.py examples\metric_log_example_2.json
```

`metric_log`는 다음 값을 자동 보강합니다.

- `이전값`이 비어 있으면 같은 `종목/업종` + `지표명`의 직전 `현재값`을 연결
- `이전값`과 `현재값`이 숫자면 `변화율` 자동 계산
- `방향`이 비어 있으면 숫자 변화로 `상향` / `하향` / `유지` 자동 판정

## TSV 출력

Google Sheet에 복사/붙여넣기 쉬운 TSV를 출력합니다.

```powershell
python scripts\export_tsv.py investment_review_log --last 5
python scripts\export_tsv.py bottleneck_log
python scripts\export_tsv.py industry_indicators --no-header
python scripts\export_tsv.py metric_log --last 5
```

## 리포트 생성

```powershell
python scripts\gen_report.py board
python scripts\gen_report.py weekly
python scripts\gen_report.py sector "메모리 반도체"
python scripts\gen_report.py share
```

metric 상세와 발굴 보드:

```powershell
python scripts\gen_report.py metric "메모리 반도체"
python scripts\gen_report.py metric
python scripts\gen_report.py metric --min 3
```

- `metric "종목/업종"`: 지표별 최신 현재값, 연속 상향 횟수, 최근 변화율, 최근 날짜 출력
- `metric`: 연속 상향 2회 이상인 `(종목/업종, 지표명)`을 횟수순으로 출력
- `metric --min N`: 발굴 보드 노출 기준을 연속 상향 N회 이상으로 조정

## 템플릿 생성

```powershell
python scripts\create_templates.py
python scripts\create_templates.py --overwrite
```

## 주의

이 저장소는 개인 리서치 기록용이며 투자 권유가 아닙니다. API 연동, 텔레그램 전송, 에이전트 자동 실행은 현재 범위 밖입니다.
