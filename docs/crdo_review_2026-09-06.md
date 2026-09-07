# CRDO 실적 재점검 및 추적 사례

현재 판단은 **사업 확산 / 단일 출처 확인 / 재검토**다. 실적 확대는 확인했지만 동일 회계연도 EPS 컨센서스의 상향 이력이 없어 시계열 검증·중기 단계로 승격하지 않았다. 과거 실적을 지금 연결한 사례이므로 조기 발견 성과로 집계하지 않는다.

| 항목 | FY26 Q4 | FY27 Q1 |
| --- | --- | --- |
| 기간 말 | 2026-05-02 | 2026-08-01 |
| 매출 (백만 USD) | 437.0 | 479.0 |
| GAAP 희석 EPS (USD) | 0.88 | 0.67 |
| non-GAAP 희석 EPS (USD) | 1.16 | 1.20 |
| GAAP 매출총이익률 | 68.2% | 64.5% |
| non-GAAP 매출총이익률 | 68.3% | 68.0% |

출처: [FY26 Q4 공식 실적](https://investors.credosemi.com/news-events/news/news-details/2026/Credo-Technology-Group-Holding-Ltd-Reports-Fourth-Quarter-and-Fiscal-Year-2026-Financial-Results/default.aspx), [FY27 Q1 공식 실적](https://investors.credosemi.com/news-events/news/news-details/2026/Credo-Technology-Group-Holding-Ltd-Reports-First-Quarter-of-Fiscal-Year-2027-Financial-Results/default.aspx).

기존에 사용한 1.16달러는 FY26 Q4 non-GAAP 확정 실적이며 FY27 Q1 컨센서스 baseline이 아니다. 같은 회사의 두 발표는 독립 출처 두 개로 세지 않는다.

FY27 Q1 매출은 종전 회사 가이던스 465~475백만 달러 상단을 넘었지만, GAAP 매출총이익률 64.5%는 종전 하단 66.9%보다 낮았다. 이는 **소급 대조**이며 미리 등록한 예측의 적중이 아니다. 회계 조정과 사업 수익성 변화를 다음 점검에서 분리한다. 회사 전망과 시장 컨센서스는 별도다. 위 공식 발표 두 건을 근거로 비교했다.

SIG-0873/0867과 14개 actual/guidance 관측을 IDEA-0002에 연결했다. 발표일과 실제 입력 관측일을 분리했고 원본 검토는 백업과 review_history에 보관했다. CRDO의 SEC 식별자는 [공식 10-K](https://www.sec.gov/Archives/edgar/data/1807794/000162828026043303/crdo-20260502.htm)의 CIK 0001807794이며 config/entities.json에서 NASDAQ:CRDO와 연결했다.

다음 점검은 2026-09-13이다. 필요한 자료는 같은 FY 컨센서스 시계열, 고객별 수요의 독립 근거, GAAP/non-GAAP 차이의 원인이다. 기존 forward PER·고객별 추정 비중은 이번에 재검증하지 않았으며 현재 판단의 수치 근거로 사용하지 않는다. FMP는 실제 조회에서 HTTP 402가 반환되어 컨센서스가 비어 있다.
