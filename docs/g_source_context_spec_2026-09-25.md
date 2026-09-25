# F 인수 검토와 G 원문 연결 지시 — Codex, 2026-09-25

기준 HEAD `2945070`. 구현 담당자는 이 문서를 기준으로 보완 R1~R3 후 G1~G4를 순서대로 별도 커밋한다. Codex의 이번 작업은 검토와 설계이며 운영 코드 수정·실종목 등록·메시지 발송은 하지 않았다.

## 1. F 검토 판정

241개 테스트를 재실행해 통과했다. 임시 Git 원격 실패를 의도적으로 만드는 테스트의 fatal 출력은 시험 시나리오이며 전체 테스트 실패가 아니다. 변이 시험 32건은 인수인계 보고이며 이번 검토에서 다시 실행하지 않았다.

이전 F 핵심 수정은 수용한다. 저장된 index는 cards-v2, 카드 30개, stale 없음이다. AMCX sent/message_id 137이 유지됐고 최신 일간 run은 `36139710587-1`이다. GitHub API나 텔레그램 화면을 이번에 별도 조회한 것은 아니다. 실제 예약→발송→영수증 저장, 사용자 /track, 승인 운영, 9/28 주간 실행은 미확인으로 유지한다. 이를 기다리느라 G 구현을 멈출 필요는 없다.

추가 판단: v1→v2 이관은 수용한다. 같은 원자료 시각에 생성기 변경으로 생긴 버전은 '데이터 재관측'과 구분해 표시한다. 관측 파일·스냅샷은 당분간 모두 보존하고 자동 삭제하지 않는다. 30일 누적 후 파일 수/용량/체크아웃 시간을 보고 보존·저장소 이전을 판단한다. 번역 원문은 웹/문서에 제공하고 텔레그램에서 생략해도 된다.

## 2. 다음 단계 전 작은 보완

### R1. 원격 보존 성공 판정

대상 `scripts/persist_state.py`, 관련 테스트. `main`은 staged diff가 없으면 push 없이 반환하고 `persist`는 True를 반환한다. 모의 실행에서 `persist=True, push_called=False`를 확인했다. 직전 commit은 성공하고 push만 실패한 상태에서 동일 내용 재호출 시 로컬 commit이 원격에 없는데 성공으로 오인할 수 있다. 현재 후보 경로는 released 재기록으로 다시 diff가 생기기도 하지만 공용 함수 계약 자체를 고쳐야 한다.

- 새 diff가 없어도 미푸시 commit을 보존해야 한다. 허용 파일만 stage/commit하되 원격 동기화 단계는 생략하지 않는다. 현재 HEAD의 대상 원격 브랜치 반영을 성공 기준으로 삼는다. 원격 push가 거절되면 False, 강제 push/자동 충돌 덮어쓰기는 금지한다.
- 실제 임시 Git 원격에서 commit 성공→push 실패→원격 연결 복구→파일 변경 없이 persist 재호출을 시험하고 원격 commit 도달을 확인한다. 원격 접근 실패인데 clean tree라는 이유로 True가 되면 안 된다.

### R2. 승인 시점의 현재 신선도

대상 `candidates.approve`, `screen_items` 호출 경계. approve는 저장 당시 index.stale만 확인한다. 생성 후 36시간 이상 지나거나 그 뒤 screen이 실패해도 index를 재생성하지 않았으면 오래된 승인 가능성이 남는다. 코드 경로 확인 사항이며 운영 재현은 하지 않았다.

- 원문/카드 승인 직전에 현재 UTC 시각, 선택 원자료 시각, 최신 daily screen 시도, 최신 사용 가능한 snapshot을 다시 검사한다. 현재 스냅샷과 index 참조가 다르면 재생성·재검토를 요구한다. 승인 검사는 네트워크/번역/원장 변경 없이 수행한다.
- 자동 후보 알림 진입 시에도 같은 공용 신선도 함수를 사용한다. 렌더 시각을 원자료 시각 대신 사용하지 않는다. query는 오래된 카드 표시를 허용하고 승인은 거부한다.
- 시험: index.stale=[]를 유지한 채 시계만 37시간 진행, 생성 뒤 screen 실패, 더 최신 snapshot 등장, 정상 현재 입력. 모든 거부에서 승인 파일 변경/전송 0.

### R3. 실제 모델 요청 예산

대상 `extract.call_gemini_prompt`, common 모델 예산 함수, 모든 호출자. 현재 record_model_call은 retry 루프 밖에 있어 한 논리 호출이 최대 네 번 HTTP 요청해도 한 번만 계수한다. G를 추가하기 전에 한도를 실제 요청 기준으로 통일한다.

- 매 HTTP 시도 직전 공용 KST 일일 잔여량과 구성요소 잔여량을 검사하고 예약·저장한다. 실패/429/재시도도 각 1회이며 예산 부족이면 네트워크 0회로 deferred_budget을 반환한다. 호출자와 전송 함수의 이중 계수는 금지한다.
- 초기 일일 총 20회는 유지한다. 정책에 extract 최대 11회, cards 번역 최대 3회, candidate_context 최대 6회를 둔다. 이 단계에서는 구성요소끼리 예산을 빌리지 않는다. 초기화/마이그레이션 때 기존 당일 계수를 지우거나 미기록 사용량을 0으로 확정하지 않는다.
- 시험: 총 19회에서 첫 요청 실패→마지막 1회 사용→재시도 0, 구성요소 한도, KST 경계, 중단 후 예약 유지, 예산 부족이어도 기존 결과 조회 가능.

## 3. G의 목적과 범위

현재 카드는 'EPS 숫자가 올라서 조건에 걸린 기업'이다. G는 후보마다 최근 공식 실적 발표·가이던스에서 **어떤 사업 변화가 있었는지, 왜 이익에 영향을 줄 수 있는지, 무엇이 아직 설명되지 않는지**를 짧게 연결한다.

회사 발표가 존재한다는 것만으로 그 발표가 애널리스트 추정치 상향을 일으켰다고 단정하지 않는다. 기본 문구는 'EPS 상향과 함께 살펴볼 회사 발표'다. 직접 인과 근거가 없으면 '상향 원인 확인'으로 표시하지 않는다. 시장 미반영·지속 성장·병목 입증도 자동 추론하지 않는다.

범위는 최신 카드 대상 A/B 합집합 최대 40개다. 전 종목 심층 조사, 기존 3종목 집중 분석, 매수/목표가/주가 예측, 새 DB·서버·공개 웹 배포, 자동 추적 등록, 자동 추천 승인은 제외한다. 사람이 확인한 candidate_evidence와 기계가 작성한 초안은 다른 저장소에 둔다.

## 4. G1 — 기업 식별과 공식 문서 수집

대상: 새 `scripts/candidate_context.py`(선정·조정), 필요하면 `scripts/company_filings.py`(수집 공통), screen_revisions, schema.json, research_policy.json, persist_state.

### 입력과 기업 연결

- cards를 입력으로 받아 cards를 다시 만드는 순환을 만들지 않는다. 최신 유효 스크린 snapshot과 공용 display_order에서 대상 ticker 목록을 구한다. latest screen이 stale/partial이면 새 외부 조사와 자동 알림은 보류하고 기존 근거는 날짜와 함께 조회한다.
- 현재 load_universe는 SEC 응답에서 ticker/거래소만 남긴다. 원자료에 있는 CIK를 검증해 별도 issuer 매핑으로 보존한다. CIK는 10자리 정규화, 매핑 출처·관측일·SHA를 기록한다. 오래된 snapshot에 CIK가 없으면 캐시된 공식 목록에서 exact ticker/거래소로 연결한다. 회사명 유사성만으로 연결하지 않는다.
- **기존 entity_id와 CAN-ID를 CIK로 일괄 교체하지 않는다.** issuer_cik는 부가 매핑이다. 서로 다른 주식 클래스는 같은 발행사 문서를 공유할 수 있으나 EPS/가격 시계열은 합치지 않는다. 기존 registry와 충돌하면 identity_conflict로 보류한다.

### 수집 경로와 한도

- 첫 구현은 SEC 제출 문서 중심이다. 기업별 submissions에서 최근 120일의 8-K/6-K 실적·전망 자료, 10-Q/10-K/20-F 관련 자료를 탐색한다. 8-K 제목만 읽지 말고 제출 문서 목록에서 실적 발표 첨부자료를 찾는다. EX-99 문서가 항상 실적 자료인 것은 아니므로 제목·본문으로 판별한다. PDF만 있거나 본문을 해석 못 하면 unsupported_content로 둔다. 표준 라이브러리 범위를 유지한다.
- Submissions API의 CIK 형식과 filings 구조는 [SEC API 설명](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)을 따른다. SEC는 사용자 전체 요청을 초당 최대 10건으로 안내한다. 이 프로젝트의 새 수집기는 더 낮은 초당 2건, 동시 1개로 시작하고 기존 SEC 요청도 같은 제한기를 공유한다. [SEC 개발자 안내](https://www.sec.gov/about/developer-resources)
- 기존 SEC_USER_AGENT 사용, 실제 값 로그 금지. 회사 IR 직접 수집은 **검증해 config에 등록한 도메인만** 선택적 보조 경로로 허용한다. 임의 검색 결과나 모델이 만든 URL을 따라가지 않는다. SEC에서 확보 불가하면 미확보로 남겨도 G1 완료 가능하다.
- 초기 policy: 신규 확인 기업 최대 10개/일, 기업별 제출 문서 목록 후보 최대 5개, 본문 최대 3개, 전체 HTTP 시도 최대 100회/일, 새 단계 시간 예산 180초, 요청 timeout 최대 15초, 원문 최대 2MB/문서. 제한은 호출 전에 검사하고 재시도·redirect도 차감한다. 429/5xx 최대 1회 재시도, Retry-After가 남은 예산보다 길면 보류. 403 반복 시 해당 공급자 수집을 멈추고 실패 원인 보존.
- 선정은 미확인 후보의 first_seen 오래된 순→동률이면 A/B 표시순→후보 ID. 신규 후보가 계속 들어와도 오래 기다린 후보가 굶지 않게 한다. 이미 조사한 후보는 7일 뒤 또는 수치 EPS/FY 변화 때 재검토 가능. 실패 재시도는 24시간 뒤, 성공적으로 '적합 문서 없음'을 확인한 것은 7일 뒤. 같은 날 여러 auto/redo도 일일 한도를 넘지 않는다.

### 데이터 계약

- `data/processed/company_documents/{DOC-id}.json.gz`: issuer 매핑, 원 URL/최종 URL, accession/form, 제목/발행자, published_at(알 수 없으면 null), filed_at, observed_at, 대상 회계기간, 원응답 SHA256, 정규화 본문, 정규화 규칙 버전. ID는 발행사+accession+문서 경로+내용 SHA로 생성한다. 같은 URL의 정정 본문은 새 DOC, 옛 DOC는 보존한다.
- `candidate_context_state.json`: 후보별 시도일, 결과 상태, 문서 참조, 다음 조사 가능 시각, 일일 요청·대상 예산. 상태는 queued/success/no_relevant_document/unavailable/failed/deferred_budget/identity_conflict. 성공·정상 미확보·기술 실패 수를 분리한다.
- HTML은 script/style/navigation을 제거하되 표의 행/열·괄호 음수·단위·기간 헤더를 잃지 않도록 파싱한다. 원문에서 위치를 찾을 수 있는 paragraph/table IDs를 생성한다. 앞부분을 잘라서 주요 전망 문단이 없는데 '문서에 없음'이라고 쓰지 않는다. 절단 시 coverage=partial을 명시한다.
- source 파일과 정책/상태를 schema 및 persist allowlist에 넣는다. 초기에는 모두 보존하며 문서 수·gzip 바이트 증가량을 보고한다.

## 5. G2 — 근거가 붙은 설명 초안

입력은 검증된 issuer 문서와 스크린의 대상 회계기간이다. 모델 호출은 하루 최대 6회(재시도 포함), 한 요청에 한 기업만 넣는다. 첫날 30개를 모두 완성하려 하지 않는다. 문서 확보와 모델 설명의 진척을 별도 표시한다.

- 문서/기간 선택 후 관련 문단을 정해 모델에 제공한다. 기존 추출기의 AI 인프라 키워드/등급 편향을 새 선정에 재사용하지 않는다. 업종 제한 없이 같은 구조로 처리한다.
- 출력 `candidate_context_history/{CTX-id}.json`: candidate_id, issuer_cik, document_ids, source 구간 IDs, input_sha, model/prompt/parser version, generated_at, context_status, claims[], limitations[], next_check[]. 기계 출력은 candidate_evidence.json을 수정하지 않는다.
- 각 claim은 한국어 문장, kind=fact/guidance/interpretation, 원문 짧은 인용, DOC-id/문단 또는 표 위치, 대상 기간, 통화/단위/GAAP 여부, driver 태그, 영향 방향(positive/negative/mixed/unknown)을 갖는다. 숫자 구조화가 확실하지 않으면 숫자를 비교 계산하지 않는다.
- driver 태그 초기값: volume, price, mix, margin_cost, capacity, backlog, buyback_sharecount, tax, fx, acquisition_disposal, one_off, accounting, unknown. 여러 원인을 함께 표시하고 일회성·주식 수 감소를 영업 성장으로 바꾸지 않는다.
- 인용은 해당 문서 본문에 실제로 있어야 한다. 단순한 숫자 포함 검사만으로는 충분하지 않다. 기간/지표/단위/부호/GAAP 여부와 같은 문단·표 행의 연결을 검사한다. 5→3 전망을 상향이라고 쓰는 결과, guidance를 actual로 쓰는 결과, 다른 FY 숫자 비교는 거부한다. 구조 검사를 통과해도 의미 검증 완료라는 명칭 대신 '자동 정리·미검토'로 표시한다.
- 회사 가이던스 상향: 같은 회사·대상 기간·지표·기준의 이전/현재 발표를 모두 확보했을 때만 변화량 계산. 이전 발표가 없으면 '현재 가이던스 제시'라고 쓴다. Yahoo EPS 기준 미표시 값을 non-GAAP 회사 전망과 직접 차감하지 않는다.
- 회사 발표와 EPS revision 사이 연결은 temporal_context/explicit_link/unconfirmed 중 하나로 기록한다. 기본 unconfirmed 또는 temporal_context. explicit_link는 실제 원문에 해당 컨센서스 수정과 사건의 연결이 명시된 경우만 허용한다. 단지 발표일이 90일 구간 안이라는 이유로 인과를 확정하지 않는다.
- 동일 실적 발표의 첨부자료와 IR 재게시를 독립 근거 2개로 세지 않는다. 일회성 요인·하향 전망·수요 둔화 등 반대 근거도 함께 추출한다. 근거가 없으면 '원문에서 확인 못 함', 수집 실패는 '원문 접근 실패'로 구분한다.
- 날짜만 있는 발표는 날짜 정밀도로 보존하고 임의 장전/장후 시각을 만들지 않는다. observed_at 이후 공개된 자료는 그 당시 설명에 소급 결합하지 않는다. 늦게 확보한 자료는 현재 생성한 CTX로만 연결한다.

## 6. G3 — 카드와 승인 흐름 연결

대상 candidates.py, templates/candidates.html, telegram_cmd.py, schema.

카드 순서: 회사 설명 → 숫자로 후보가 된 이유 → **공식 발표에서 확인한 변화(자동 정리·미검토)** → 이익에 연결될 수 있는 경로(해석) → 일회성/반대 근거/인과 미확인 → 다음 확인 → 출처/추적 명령.

- 자동 근거 요약은 최대 3문장, 제한/반증 2개, 다음 점검 1개로 시작한다. 출처를 펼치면 원문 인용·실제 날짜·기간·문서 링크가 나온다. 자료가 없는 후보도 숫자 카드와 추적 기능은 유지한다.
- research_status=not_started/queued/source_linked/draft_ready/review_needed를 자료 품질과 별도 표시한다. 이 상태가 found를 recommended로 바꾸지 않는다. 기존 사람이 승인한 문구를 자동 출력으로 덮어쓰지 않는다.
- 새 CTX가 카드의 주장을 바꾸면 candidate_version에 context_id/input_sha를 반영한다. generated_at만 바뀌면 새 버전/알림을 만들지 않는다. 관측의 EPS 관측일과 CTX 생성일을 분리한다. 과거 관측에서 최신 CTX를 끌어오지 않는다.
- 승인/철회는 시장 데이터 관측과 다른 사건이다. 동일 snapshot/version에서 승인만 바뀌어도 immutable observation을 덮어쓰지 말고 별도 append-only review event에 승인자·시간·근거 해시·대상 관측/버전을 보관한다. 과거 카드 재현은 조회 기준시각의 승인 상태를 사용하고 현재 추적 상태는 별도로 표시한다.
- 자동 초안→사람 확인은 명시적인 copy/import CLI로 candidate_evidence에 복사하되 approval은 복사하지 않는다. 다섯 설명 항목에 충분하지 않은 곳은 빈 채로 남긴다. 사람이 채우고 재생성·검토한 뒤 기존 approve를 호출한다. 모델이 승인자 이름을 넣거나 승인 명령을 실행하지 않는다.
- 신규 CTX 자체는 추가 텔레그램 발송 사유가 아니다. 기존 신규 발견/수동 추천 승인 이벤트와 일일 3개·기업 간격을 유지한다.

## 7. G4 — 실행 연결과 검증

- 순서 screen → candidate_context → cards → alerts → views. context는 screen 결과/조사 상태를 입력으로 사용하고 cards는 context 출력을 읽는다. context 실패는 숫자 카드·기존 종목 수집·위험 알림을 막지 않는다. 실패 상태/마지막 근거는 화면에 표시한다. daily_run_state에 입력 관계와 generator/policy version을 등록한다.
- queued/deferred_budget는 기술 실패가 아니다. 일부 문서 접근 실패는 quality=partial로 기록하고 24시간 재시도 규칙을 쓴다. generic partial retry로 60분마다 이 단계를 다시 조사하지 않도록 단계별 정책을 명시한다. commands는 외부 원문/모델 호출을 하지 않는다.
- 현재 job 한도는 40분이다. 기존 screen 자체 25분 예산과 다른 단계 소요를 포함해 확인한다. 새 context는 180초 안에서 중단·저장하고 job 종료 전 최소 2분을 상태 보존용으로 남긴다. 최악 경로가 40분을 넘으면 실제 계산 근거를 남기고 workflow 한도만 필요한 만큼 조정한다. 제한 없는 수집/예산 자동 확대는 금지한다.

필수 시험:

1. 정확한 CIK 연결, 동명이인·복수 클래스·거래소 충돌, 기존 CAN-ID 유지.
2. 관련 없는 EX-99, 실적 첨부 문서, 6-K, PDF만 있는 자료, 표/괄호 음수, 수정 공시, 중복 재게시.
3. 가이던스 상향/하향/유지/첫 제시, FY와 GAAP 불일치, 주식 수·세금·일회성 이익, 원문 없는 인용·숫자·인과 단정 거부.
4. 429/403/연결 중단/다운로드 크기/일일 요청·모델 예산·180초 만료, 다음 날 순환 처리, 모델 키 없음, 동일 문서 캐시 적중.
5. CTX/관측/승인 사건의 과거 재현, 자동 초안이 추천/원장 등록/메시지를 만들지 않음, stale 화면, 조회 경로 외부 호출 0.
6. 워크플로 순서, context 실패해도 cards/위험 알림 독립, 같은 날 반복 auto 예산 유지, Windows/CI 해시 일치, 기존 241개 회귀.

완료 증거:

- G1/G2/G3/G4 각 커밋, schema/policy 변경표, 테스트 결과, 실패 주입 결과.
- 현재 실제 후보 최소 6개를 서로 다른 업종에서 선정해 수집·초안 검증. 성공 사례만 골라 숨기지 말고 선정 목록/실패/미확보까지 공개한다. 기업별 문서 1~3개, 실제 원문 인용과 요약의 대조, 이익 연결의 미확인 부분을 기록한다. 새 실종목 등록/검증용 메시지 발송은 하지 않는다.
- 운영 첫 실행은 자동 메시지 추가 없이 저장된 G 결과와 다음 반복 실행의 캐시/예산을 확인한다. 데스크톱 1280px·모바일 390px에서 운영 자료 사본으로 새 구역을 확인한다. coverage를 '카드 30개 중 원문 연결 N, 초안 N, 미확보 N, 대기 N'으로 보고한다.

G의 완료는 모든 후보의 상향 원인을 설명해낸다는 뜻이 아니다. **근거가 있으면 출처와 한계가 함께 보이고, 없으면 무엇을 더 확인해야 하는지 남는 것**이 완료 기준이다. 이후 종목별 관측 페이지 설계로 진행한다.
