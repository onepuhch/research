# Reddit Watch Google Sheets 연동 설정

이 설정은 GitHub의 CSV를 하나의 Google 스프레드시트에 동기화합니다. Reddit 관심 종목은 매주 누적하고, 발굴 신호와 투자 리뷰 현황은 매일 갱신합니다.

## 1. 스프레드시트 만들기

1. [Google Sheets](https://sheets.google.com)에서 **빈 스프레드시트**를 새로 만듭니다.
2. 파일 이름은 원하는 이름으로 정합니다. 예: `Investment Reddit Watch`.
3. 필요한 탭은 스크립트가 자동으로 만들기 때문에 미리 만들지 않아도 됩니다.

## 2. Apps Script 편집기 열기

1. 새로 만든 스프레드시트 상단 메뉴에서 **확장 프로그램**을 누릅니다.
2. **Apps Script**를 누릅니다.
3. 새 탭에서 Apps Script 편집기가 열립니다.

## 3. GAS 코드 두 개 붙여넣기

1. 편집기 왼쪽의 `코드.gs` 파일을 엽니다.
2. 기본으로 들어 있는 코드를 모두 지웁니다.
3. 이 저장소의 [`docs/gas_reddit_watch.js`](gas_reddit_watch.js) 내용을 전부 붙여넣습니다.
4. 왼쪽 파일 목록 옆의 **+** 버튼을 누르고 **스크립트**를 선택합니다.
5. 새 파일 이름을 `gas_main`으로 정합니다.
6. 이 저장소의 [`docs/gas_main.js`](gas_main.js) 내용을 새 파일에 전부 붙여넣습니다.
7. `SHEET_ID`는 두 파일이 공유합니다. `gas_main`에 선언된 값만 다음 단계에서 수정합니다.

## 4. SHEET_ID 입력하기

스프레드시트 URL은 다음과 비슷합니다.

```text
https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890/edit#gid=0
```

1. URL에서 `/d/`와 `/edit` 사이의 문자열을 복사합니다.
2. 위 예시의 스프레드시트 ID는 `1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890`입니다.
3. Apps Script의 `gas_main` 파일 맨 위에 있는 상수를 다음처럼 수정합니다.

```javascript
const SHEET_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz1234567890";
```

4. 상단의 **프로젝트 저장** 아이콘을 누르거나 `Ctrl+S`를 누릅니다.

## 5. 탭 구조

스크립트가 같은 스프레드시트에 다음 탭을 자동 생성합니다.

| 탭 | 원본 CSV | 동기화 방식 |
|---|---|---|
| `reddit_watch` | `data/processed/reddit_watch.csv` | `날짜 + 종목후보`가 없는 행만 누적 |
| `signal_log` | `data/processed/signal_log.csv` | `signal_id`가 없는 행만 누적 |
| `investment_review_log` | `data/processed/investment_review_log.csv` | `idea_id`가 같으면 기존 행 업데이트, 없으면 추가 |

탭의 첫 행은 GitHub CSV 헤더와 같아야 합니다. 헤더 이름이나 순서를 시트에서 직접 바꾸면 동기화가 중단됩니다.

## 6. 첫 실행과 권한 승인

1. 편집기 상단의 함수 선택 목록에서 `runAll`을 선택합니다.
2. **실행**을 누릅니다.
3. 처음 실행할 때 권한 승인 창이 나타납니다.
4. 사용할 Google 계정을 선택합니다.
5. 경고 화면이 나오면 **고급**을 누른 뒤 프로젝트로 이동합니다.
6. 외부 CSV 읽기와 스프레드시트 수정 권한을 확인하고 **허용**을 누릅니다.
7. 실행이 끝나면 스프레드시트에 `signal_log`와 `investment_review_log` 탭이 생성됐는지 확인합니다.
8. 함수 선택 목록에서 `importRedditWatch`도 한 번 실행해 `reddit_watch` 탭을 생성합니다.
9. Apps Script 하단의 **실행 로그**에서 추가, 업데이트, skip 건수를 확인합니다.

## 7. 매일 현황판 트리거 설정

1. Apps Script 편집기 왼쪽의 시계 모양 **트리거**를 누릅니다.
2. 오른쪽 아래의 **트리거 추가**를 누릅니다.
3. 다음과 같이 설정합니다.

| 설정 | 값 |
|---|---|
| 실행할 함수 | `runAll` |
| 실행할 배포 | `Head` |
| 이벤트 소스 | 시간 기반 |
| 시간 기반 트리거 유형 | 일 단위 타이머 |
| 시간대 | 오전 10시~11시 등 GitHub 일일 실행 이후 |

4. **저장**을 누릅니다. 이 트리거 하나가 `signal_log` 동기화 후 `investment_review_log` 동기화를 순서대로 실행합니다.

## 8. 매주 월요일 Reddit 트리거 설정

1. Apps Script 편집기 왼쪽의 시계 모양 **트리거**를 누릅니다.
2. 오른쪽 아래의 **트리거 추가**를 누릅니다.
3. 다음과 같이 설정합니다.

| 설정 | 값 |
|---|---|
| 실행할 함수 | `importRedditWatch` |
| 실행할 배포 | `Head` |
| 이벤트 소스 | 시간 기반 |
| 시간 기반 트리거 유형 | 주 단위 타이머 |
| 요일 | 월요일 |
| 시간대 | 원하는 오전 시간대 |

4. **저장**을 누릅니다.

Google Apps Script의 시간 기반 트리거는 선택한 시간대 안에서 실행 시각이 조금 달라질 수 있습니다. GitHub의 월요일 수집이 끝난 뒤 실행되도록 오전 10시 이후 시간대를 선택하는 것이 안전합니다.

## 9. 동작 확인

매일 실행 후 `signal_log`와 `investment_review_log` 탭을 확인합니다. 다음 주 월요일 실행 후에는 `reddit_watch` 탭의 마지막 행을 확인합니다. 중복 키는 다시 추가하지 않으며, Apps Script 실행 로그에 추가, 업데이트, skip 건수가 표시됩니다.

오류가 발생하면 먼저 다음을 확인합니다.

- `SHEET_ID`가 비어 있지 않은지
- 스프레드시트 URL에서 ID만 정확히 복사했는지
- `reddit_watch` 탭의 첫 행 헤더를 수동으로 변경하지 않았는지
- GitHub raw URL이 브라우저에서 열리는지
