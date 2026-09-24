# AI 연결 병목: 랙 내부 fabric 전환의 증분 이익은 누구에게 귀속되는가

기준일 2026-09-24 / 생성일 2026-09-24

AI 연결 병목: 랙 내부 fabric 전환의 증분 이익은 누구에게 귀속되는가
9월 24일 재점검: 세 기업의 분기 컨센서스를 확보했다. 매출 예상치는 회사 전망 중간값에 가까워 전망 달성만으로 시장 미반영 우위를 입증할 수 없다. ALAB 메모리 연결 샘플링·CRDO 1.6T 광제품·MRVL 광 시연은 메커니즘 근거이며 독립 이익 우위는 미확인. 관찰·재검토 유지.
미완성 연결 4개 / 다음 점검 2026-09-28 (예정)

## 인과 연결과 빈칸

| 주장 | 판정 | 근거 | 한계 |
| --- | --- | --- | --- |
| AI 시스템이 연결·대역폭 확장을 요구한다 | 확인 | AWS-TRN3, NV-CPO | 고객 제품 사양과 공급 계획 확인. 실측 병목 강도·이용률은 없음. |
| 병목의 경제적 가치가 랙 내 fabric과 신호 처리로 이동한다 | 추론 | ALAB-Q2, AWS-TRN3, ALAB-LEO | 시스템 요구와 제품 전환의 연결 가설. 특정 고객→특정 공급사 계약은 확인하지 않음. |
| 지속적인 공급 부족이 가격 결정력을 만든다 | 미확인 | CRDO-10Q-Q1, ALAB-10Q-Q1 | CRDO의 생산능력 예약 약정은 확인했으나 실제 부족량·납기·가격 결정력은 미확인. ALAB의 과거 평균판매가격 상승은 제품 믹스 효과여서 동일 제품 가격 인상으로 볼 수 없음. |
| 후보 기업의 매출·이익으로 연결된다 | 추론 | ALAB-Q2, CRDO-Q1, MRVL-Q2, CRDO-ZF16 | 전사 실적은 확인. 제품별 증분 이익과 고객별 귀속은 미완료. |
| 현재 시장 기대에 충분히 반영되지 않았다 | 미확인 |  | 9월 24일 분기 예상 매출이 회사 전망 중간값에 가까움을 확인. 신제품별 물량·단가·기여 이익이 없어 독립 EPS 우위는 미확인. |
| 모든 연결 부품에 동일한 수혜가 발생한다 | 반증 | NV-CPO, CRDO-Q1, MRVL-INFRA, MRVL-ECOC | CPO와 구리·광 혼합 구조는 부품별 대체와 차별화를 만든다. 수요 증가와 기존 제품의 이익 증가는 동일하지 않음. |

## 후보 비교 — 연구 순서이며 매매 추천이 아님

랙 내부 fabric, 구리·광 연결, 복합 연결 반도체의 서로 다른 이익 경로를 비교하기 위한 3개사다. 전체 시장에서 가장 저평가된 기업을 선별한 결과가 아니다. AWS·NVIDIA는 고객 아키텍처/대체 기술 근거로 사용하며 특정 후보와의 공급 계약을 추정하지 않는다.

| 기업 | 우선순위 | 이익 연결 | 공개 기대와 차이 | 다음 확인 | 반증 |
| --- | --- | --- | --- | --- | --- |
| ALAB | 메커니즘 검증 | 랙 내 연결 복잡성 증가 → fabric switch 채택 → Scorpio 출하·제품 믹스 → 매출과 이익. 실제 점유율·고객별 매출 연결은 추가 확인. | 연간 EPS는 9월 9일 대비 변화 없음. 참고 PER만으로 우위를 판정하지 않는다. MRVL의 PCIe scale-up switch 전시 계획까지 고려해 Scorpio 채택·제품별 이익 귀속을 검증한다. | Q3 Scorpio 최대 제품군 전환, 매출 560백만 USD 상회 여부와 non-GAAP 총마진 72% 유지 여부를 함께 대조. 상회만으로 컨센서스 초과라고 판단하지 않는다. | Q3 매출 540백만 USD 미달, Scorpio 전환 지연, 또는 고객 아키텍처에서 외부 fabric 채택 취소 시 가설 약화. |
| CRDO | 기대·가격 비교 우선 | 연결 속도·전력 요구 증가 → AEC·광·retimer 구성 변화 → 제품별 매출·마진. 구리 단일 순수 수혜로 가정하지 않는다. | 9월 14일 FY27·FY28 EPS는 6.30217·9.67107 USD로 baseline 대비 +0.455%·+0.468%. 상향은 확인되나 지속성·독립 이익 우위는 미확인. 낮은 상대 PER을 저평가 확정으로 쓰지 않는다. | FY27 Q2 매출 535백만 USD 상회 여부, non-GAAP 총마진 67% 이상, 제품별 유기적 성장과 인수 효과 분리. | FY27 Q2 매출 525백만 USD 미달, non-GAAP 총마진 67% 미달 또는 대체 아키텍처의 실질적인 콘텐츠 축소. |
| MRVL | 분산 노출 비교 | 연결 반도체와 커스텀 실리콘 투자가 함께 실적에 반영된다. 전사 성장률을 연결 부문의 성장률로 대체하지 않는다. | FY27·FY28 EPS는 baseline 대비 +0.268%·+0.177%. 다음 분기 시장 매출 약 3149.65백만 USD·EPS 1.10038은 회사 전망 중간값 3150·1.10과 사실상 일치한다. 전망 달성 자체는 추가 우위가 아니다. | 10월 6일 투자자 행사에서 연결·커스텀 성장 기여를 분리하고, 다음 실적의 매출 전망 달성·마진을 확인. 행사일은 회사 발표 일정이다. | 연결 실적 둔화를 커스텀 성장으로 가리는 경우, 고객 내재화·경쟁 공급 확대 또는 마진 악화. |

## 동일 정의 컨센서스 관측

기업별 대상 연도가 다르므로 EPS 절대값으로 기업의 저평가 순서를 정하지 않습니다.

| 기업 | 제공자 대상 기간 말 | EPS | 기준 | 출처 | 관측일 | 관측일 수 | 연속 월간 순상향 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ALAB | 2026-12-31 | 4.0322 | non-GAAP | [Yahoo Finance non-GAAP](https://finance.yahoo.com/quote/ALAB/analysis/) | 2026-09-24 | 16 |  |
| ALAB | 2027-12-31 | 6.39348 | non-GAAP | [Yahoo Finance non-GAAP](https://finance.yahoo.com/quote/ALAB/analysis/) | 2026-09-24 | 16 |  |
| CRDO | 2027-04-30 | 6.30509 | non-GAAP | [Yahoo Finance non-GAAP](https://finance.yahoo.com/quote/CRDO/analysis/) | 2026-09-24 | 17 |  |
| CRDO | 2028-04-30 | 9.70487 | non-GAAP | [Yahoo Finance non-GAAP](https://finance.yahoo.com/quote/CRDO/analysis/) | 2026-09-24 | 17 |  |
| MRVL | 2027-01-31 | 4.2113 | non-GAAP | [Yahoo Finance non-GAAP](https://finance.yahoo.com/quote/MRVL/analysis/) | 2026-09-24 | 16 |  |
| MRVL | 2028-01-31 | 6.75725 | non-GAAP | [Yahoo Finance non-GAAP](https://finance.yahoo.com/quote/MRVL/analysis/) | 2026-09-24 | 16 |  |


## 가격과 시장 기대

정규장 최종 시세와 최신 연간 non-GAAP EPS의 참고 비교입니다. 거래 시각과 EPS 관측일이 다를 수 있으며, 아래 PER은 동시점 역사적 밸류에이션이나 적정가치가 아닙니다. 대상 회계연도가 달라 기업 간 단순 순위로 사용하지 않습니다. 시세는 정규장 체결값이며 종가 경매 가격을 보장하지 않습니다.

| 기업 | EPS 대상 기간 말 | EPS / 관측일 | USD 시세 / 거래시각 UTC | 참고 PER | 동일 기간 EPS 변화 | 시세 수집시각 |
| --- | --- | --- | --- | --- | --- | --- |
| ALAB | 2026-12-31 | [4.03220](https://finance.yahoo.com/quote/ALAB/analysis/) / 2026-09-24 | [352.73](https://query1.finance.yahoo.com/v8/finance/chart/ALAB?range=5d&interval=1d) / 2026-09-24T14:51:04+00:00 | 87.48 | +0.000% (최초 2026-09-09) | 2026-09-24T23:51:58.850927+09:00 |
| ALAB | 2027-12-31 | [6.39348](https://finance.yahoo.com/quote/ALAB/analysis/) / 2026-09-24 | [352.73](https://query1.finance.yahoo.com/v8/finance/chart/ALAB?range=5d&interval=1d) / 2026-09-24T14:51:04+00:00 | 55.17 | +0.000% (최초 2026-09-09) | 2026-09-24T23:51:58.850927+09:00 |
| CRDO | 2027-04-30 | [6.30509](https://finance.yahoo.com/quote/CRDO/analysis/) / 2026-09-24 | [190.26](https://query1.finance.yahoo.com/v8/finance/chart/CRDO?range=5d&interval=1d) / 2026-09-24T14:51:56+00:00 | 30.18 | +0.502% (최초 2026-09-07) | 2026-09-24T23:51:58.696868+09:00 |
| CRDO | 2028-04-30 | [9.70487](https://finance.yahoo.com/quote/CRDO/analysis/) / 2026-09-24 | [190.26](https://query1.finance.yahoo.com/v8/finance/chart/CRDO?range=5d&interval=1d) / 2026-09-24T14:51:56+00:00 | 19.60 | +0.819% (최초 2026-09-07) | 2026-09-24T23:51:58.696868+09:00 |
| MRVL | 2027-01-31 | [4.21130](https://finance.yahoo.com/quote/MRVL/analysis/) / 2026-09-24 | [254.47](https://query1.finance.yahoo.com/v8/finance/chart/MRVL?range=5d&interval=1d) / 2026-09-24T14:51:57+00:00 | 60.43 | +0.244% (최초 2026-09-09) | 2026-09-24T23:51:59.002260+09:00 |
| MRVL | 2028-01-31 | [6.75725](https://finance.yahoo.com/quote/MRVL/analysis/) / 2026-09-24 | [254.47](https://query1.finance.yahoo.com/v8/finance/chart/MRVL?range=5d&interval=1d) / 2026-09-24T14:51:57+00:00 | 37.66 | +0.542% (최초 2026-09-09) | 2026-09-24T23:51:59.002260+09:00 |


## 시장 기대 재점검

아래 연구자 해석의 기준일은 2026-09-24. 9월 16일·18일 예약된 수동 점검은 오늘 수행했으며 소급 기록하지 않았다.

이번에 세 기업의 동일 분기 시장 예상치를 확보했다. 매출은 백만 USD, EPS는 USD non-GAAP이다. 출처는 각 기업 Yahoo analysis 페이지이며 실제 조회 시각과 분석가 수는 원장·원자료에 보존했다.

| 기업 | 대상 분기 말 | EPS 예상 | 매출 예상 | 회사 전망 중간값 | 매출 차이 |
| --- | --- | --- | --- | --- | --- |
| ALAB | 2026-09-30 | 1.19161 | 550.6363 | 550 | +0.116% |
| CRDO | 2026-10-31 | 1.28252 | 531.7557 | 530 | +0.331% |
| MRVL | 2026-10-31 | 1.09978 | 3149.2233 | 3150 | -0.025% |

ALAB의 Leo 신제품은 샘플링 단계로 구분한다. CRDO의 1.6T 광 제품 발표는 구리뿐 아니라 광 연결로의 확장을 확인하지만 산업 전체 출하 전망을 CRDO 판매량으로 대입하지 않는다. MRVL의 광 시연은 경쟁 기술 경로이며 계약이나 매출 실현을 뜻하지 않는다.

독립 추정: 제품별 판매량×단가→매출, 제품별 원가·비용→영업이익, 이자·세금·희석주식수→EPS 입력 중 판매량·단가·제품 마진이 부족하다. 따라서 기존 회사 전망 기반 민감도는 유지하되 새로운 독립 EPS 숫자는 생성하지 않는다.

주가 성과 계산을 구현했다. 최초 스냅샷 이후 종가와 조정 시계열·SPY를 사용한다. 첫 30일 예정일은 10월 14일로 현재 평가 대기다.
## 사전 등록한 반증 점검

미래 실적이 없으면 자료 부족입니다. 회사 전망과 시장 컨센서스 초과 여부는 별개입니다.

| 기업 | 등록일 | 대상 기간 | 조건 | 기준 | 현재 결과 |
| --- | --- | --- | --- | --- | --- |
| ALAB | 2026-09-09 | 2026-09-30 | Q3 매출이 회사 전망 하단 미달 | 540 | 자료 부족 |
| ALAB | 2026-09-09 | 2026-09-30 | Q3 총마진이 회사 전망 72% 미달 | 72 | 자료 부족 |
| CRDO | 2026-09-09 | 2026-10-31 | FY27Q2 매출이 회사 전망 하단 미달 | 525 | 자료 부족 |
| CRDO | 2026-09-09 | 2026-10-31 | FY27Q2 non-GAAP 총마진 하단 미달 | 67 | 자료 부족 |
| MRVL | 2026-09-09 | 2026-10-31 | FY27Q3 매출이 회사 전망 하단 미달 | 2992.5 | 자료 부족 |
| MRVL | 2026-09-09 | 2026-10-31 | FY27Q3 non-GAAP 총마진 하단 미달 | 57.5 | 자료 부족 |

## 다음 연구 행동

- 9월 28일: ECOC 종료 후 고객 채택·물량·단가 자료 및 분기 컨센서스 재점검.
- 10월 6일: MRVL 투자자 행사에서 연결·커스텀별 매출과 마진 귀속 확인.
- 10월 14일 이후 첫 30일 주가 성과 평가. 발표된 확정 실적만 원래 반증 조건과 대조.

## 출처 원장

공급자 발표는 독립 고객 채택 증거가 아닙니다. 날짜 없는 제품 페이지는 기준일에 확인한 자료이며 발표일을 추정하지 않았습니다.

| ID | 원출처 그룹 | 역할 | 발표일 | 확인 사실 | 원문 |
| --- | --- | --- | --- | --- | --- |
| AWS-TRN3 | AWS | 고객 아키텍처 | 미표기 | Trainium3 UltraServer의 연결·메모리 대역폭 확장 구조를 공개한다. 특정 후보 공급사의 납품 증거는 아니다. | [출처](https://aws.amazon.com/ec2/instance-types/trn3/) |
| NV-CPO | NVIDIA | 경쟁·대체 기술 | 미표기 | CPO를 스위치 ASIC에 통합하는 구조와 2026년 하반기 공급 계획을 공개한다. 이미 모든 시스템에 확산됐다는 뜻은 아니다. | [출처](https://www.nvidia.com/en-us/networking/products/silicon-photonics/) |
| ALAB-Q2 | ALAB | 공급자 실적·전망 | 2026-08-04 | Q2 매출 392.4백만 USD, non-GAAP 총마진 73.7%. Q3 매출 전망 540~560백만 USD. Scorpio가 Q3 최대 제품군이 될 것으로 전망한다. | [출처](https://ir.asteralabs.com/news-releases/news-release-details/astera-labs-reports-second-quarter-2026-financial-results) |
| CRDO-Q1 | CRDO | 공급자 실적·전망 | 2026-09-01 | FY27 Q1 매출 479백만 USD, non-GAAP 총마진 68.0%. 다음 분기 매출 전망 525~535백만 USD. 구리와 광 제품을 함께 보유한다. | [출처](https://investors.credosemi.com/news-events/news/news-details/2026/Credo-Technology-Group-Holding-Ltd-Reports-First-Quarter-of-Fiscal-Year-2027-Financial-Results/default.aspx) |
| MRVL-Q2 | MRVL | 공급자 실적·전망 | 2026-08-27 | FY27 Q2 매출 2739백만 USD, non-GAAP 총마진 58.9%. 다음 분기 매출 전망 3150백만 USD ±5%. 데이터센터에는 연결과 커스텀 사업이 함께 포함된다. | [출처](https://investor.marvell.com/news-events/press-releases/detail/1031/marvell-technology-inc-reports-second-quarter-of-fiscal-year-2027-financial-results) |
| MRVL-INFRA | MRVL | 경쟁 제품·행사 계획 | 2026-09-09 | 9월 15~17일 AI Infra Summit에서 PCIe 6.0 256-lane scale-up switch 등 전시 계획. ALAB의 fabric 이익 독점은 가정할 수 없으며 실제 고객 계약·매출은 미입증. | [출처](https://investor.marvell.com/news-events/press-releases/detail/1032/marvell-to-showcase-end-to-end-ai-data-center-connectivity-portfolio-at-ai-infra-summit-2026) |
| CRDO-SEC-Q1 | CRDO | 기존 실적 원문 재확인 | 2026-09-01 | 다음 분기 non-GAAP 비용 전망 100~105백만 USD. 회사 발표와 동일 원출처로 독립 증거를 추가한 것이 아니다. | [출처](https://www.sec.gov/Archives/edgar/data/1807794/000162828026059795/credoq12027ex-991.htm) |
| CRDO-EVENTS | CRDO | 행사 일정 확인 | 미표기 | 9월 10일 Goldman Sachs 행사 일정 확인. 발표 내용의 녹취 원문은 확보하지 못해 신규 계약·가이던스 변경을 추정하지 않는다. | [출처](https://investors.credosemi.com/news-events/events/) |
| ALAB-EVENTS | ALAB | 행사 일정 확인 | 미표기 | 9월 9일 Citi 행사 일정 확인. 행사 내용 미검증; 행사 개최만으로 가설을 강화하지 않는다. | [출처](https://ir.asteralabs.com/news-events/events-presentations) |
| CRDO-10Q-Q1 | CRDO | 생산능력 확보 약정·집중 위험 | 2026-09-02 | 2~6년 조립 생산능력 예약 계약. 8월 1일 환급 가능 예치금 88.4백만 USD, 이후 추가 계약의 FY27 지급 예정액 102.4백만 USD. 분기 매출의 계약 상대방 A 43%, B 28%. 고객명·제품별 물량은 미확인. | [출처](https://www.sec.gov/Archives/edgar/data/1807794/000162828026060111/crdo-20260801.htm) |
| ALAB-10Q-Q1 | ALAB | 매출 증가의 물량·믹스 경로 | 2026-05-06 | 2026년 1분기 매출 증가를 출하량 증가와 하드웨어 모듈·Scorpio 비중에 따른 평균판매가격 상승으로 설명. 같은 제품의 가격 인상이나 최신 분기 물량으로 대체하지 않음. | [출처](https://ir.asteralabs.com/static-files/036e5de3-0bd5-4e0b-ba40-8b1cea7dbad1) |
| ALAB-LEO | ALAB | 제품·경쟁 경로 보완 | 2026-09-15 | Leo X와 Leo 2 제품군 발표 및 하이퍼스케일러 샘플링. 고객명별 생산 매출이나 단가는 미공개. | [출처](https://www.asteralabs.com/news/astera-labs-bolsters-leo-smart-memory-controller-family-for-agentic-ai-and-general-purpose-cloud-workloads/) |
| CRDO-ZF16 | CRDO | 제품·경쟁 경로 보완 | 2026-09-15 | 224G 기반 1.6T ZeroFlap 광 트랜시버 발표, DSP·SiPho PIC·진단 소프트웨어 결합. 제품별 실제 매출은 미확인. | [출처](https://investors.credosemi.com/news-events/news/news-details/2026/Credo-Expands-ZeroFlap-Portfolio-with-224G-Based-1-6T-Optical-Transceivers-Addressing-the-Growing-Demand-for-AI-Network-Infrastructure/default.aspx) |
| MRVL-ECOC | MRVL | 제품·경쟁 경로 보완 | 2026-09-20 | 2nm 광 기술과 CPO 시연 발표. 본문 날짜 9월 20일, 뉴스 목록 9월 21일, 검색 결과 9월 17일로 표기가 달라 본문을 기준으로 보존. 시연과 생산 매출은 구분. | [출처](https://www.marvell.com/company/newsroom/marvell-industry-first-2nm-optical-technology-ai-data-center-infrastructure-ecoc-2026.html) |
