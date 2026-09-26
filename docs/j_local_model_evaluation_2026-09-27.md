# J3 로컬 모델 평가 — qwen3.5:9b, 저장된 10문서·20사례 (2026-09-27)

작성: Claude, 2026-09-27 01:00 KST 무렵. 지시서: [J 지시서](j_ops_and_local_model_spec_2026-09-27.md) 4절.

**판정: 현재 보류.** 원문 초안 보조로는 기준에 크게 못 미친다.

- JSON 형식과 속도는 충분했다.
- 그러나 모델이 프롬프트 규칙을 지키지 못해 97개 주장 중 6개만 기계 검증을 통과했다.
- eval에서 **기계 검증을 통과한 중대 오류가 1건**(NBR-B 귀속 주체) 나왔다.
- 이 판정은 원문 초안 작업에만 해당한다. 번역·정리 능력은 이번에 검증하지 않았다.
- Gemini와의 우열은 **미판정**이다. 같은 입력으로 v4/v5 검증한 Gemini 출력이 아직 없다.

## 1. 환경과 재현

| 항목 | 값 |
|---|---|
| Ollama | 0.34.4, 공식 winget 패키지 `Ollama.Ollama`. 서버 `ollama serve`를 숨김 실행 |
| 서버 설정 | 127.0.0.1:11434만 수신, OLLAMA_NO_CLOUD=1, OLLAMA_NUM_PARALLEL=1, OLLAMA_MAX_LOADED_MODELS=1 |
| 모델 | `qwen3.5:9b`, digest `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`, Q4_K_M, 9.7B, 파일 6.59GB |
| 모델 위치 | `C:\Users\wls15\.ollama\models` (저장소·OneDrive 밖) |
| GPU | RTX 4070 12GB, 드라이버 560.94(CUDA 12.6). 전부 GPU 적재(size_vram = size = 6.01GB), CPU offload 없음 |
| 설정(고정) | num_ctx 16384, num_predict 3072, temperature 0, seed 42, think false, stream false, JSON schema `format` |
| 검증기 | 실행 당시 context-check-v4. 이후 v5로 오프라인 재검증(3절) |

사용자가 설치 직후 뜬 창에서 Ollama 계정 로그인을 했다. 시험 서버는 클라우드 기능이 꺼진 별도 프로세스로 돌았고, 계정은 시험에 쓰이지 않았다.

재현 명령:

```text
python scripts/local_context_benchmark.py prepare --source-data reports/generated/local_model/source_2026-09-27 --manifest tests/fixtures/local_context_benchmark/manifest.json
python scripts/local_context_benchmark.py run --experiment reports/generated/local_model/j3-55774e6d13-context-check-v4 --model qwen3.5:9b --label final --resume
python scripts/local_context_benchmark.py run --experiment <같은 폴더> --model qwen3.5:9b --label stability --cases PBF-B MPC-B DK-B NBR-A --resume
python scripts/local_context_benchmark.py report --experiment <같은 폴더> --labels tests/fixtures/local_context_benchmark/review_labels.json --output <같은 폴더>/report
```

- 실험 폴더(git 제외, 938KB): `reports/generated/local_model/j3-55774e6d13-context-check-v4/`.
  - 결과 파일 28개(요청별 원응답·파싱 결과·검증 결과·계측), runs 해시 앞 16자리 `4b68573ce332c23f`
  - requests.jsonl, manual_review.json, report.json/md
- 원문 사본: `reports/generated/local_model/source_2026-09-27/`. 문서별 file/raw/blocks 해시는 manifest에 고정했다. prepare가 확인한 결과 dataset_missing은 0이다.
- 정답표와 20사례 정의는 **모델 출력을 보기 전에** 커밋했다(320e37d).

## 2. 요청 한도

26회 상한 중 **25회**를 썼다.

- 설정 점검용 버린 dev 1회(AMCX-B)
- final 20회
- stability 4회

설정 조정은 하지 않았다. 추론 시간 합계는 341초로, 45분 상한 안이다. 실패·timeout·OOM은 0건이다. 모든 응답이 완료 사유 `stop`으로 끝났다.

| 계측 | 값 |
|---|---|
| 모델 로딩(첫 적재) | 3.8초. 이후 요청의 load_duration은 0.004초 이하 |
| 요청당 시간 (warm) | 중앙값 17.8초, p95 21.2초, 최대 24.1초 |
| 입력 토큰 | 916~5,298 (중앙값 2,268) |
| 출력 토큰 | 609~1,517 (중앙값 1,053) |
| 생성 속도 | 중앙값 64 토큰/초 |
| GPU 사용 최고치 | 8,175 MiB. 시험 전 약 1.0GB를 쓰고 있었으므로 모델이 약 7GB를 쓴 것이다 |
| API 비용 | 0. 전기·PC 점유 비용은 측정하지 않았다 |

## 3. 결과

분모 기준:

- "원문 대조 정답"은 기계 수용 주장만 원문과 대조한 결과다. 자동 매칭하고, 매칭되지 않은 것은 손으로 대조했다.
- 회수율의 "입력"은 그 사례 발췌에 실제로 들어 있던 중요 사실이다.

| 구분 | 사례 | JSON/스키마 | 모델 주장 | 기계 수용 | 원문 대조 정답 | 수용됐지만 틀림 | 중대 오류 수용 | 중대 오류(생성·거부됨) | 핵심 초안/가능 | 근거 부족 보류 | 중요 사실 회수(모델/수용) | 반대 근거 회수(모델) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| eval | 16 | 16 (100%) | 77 | 4 | 3 (75%) | 1 | 1\* | 5 | 2/14 | 2/2 | 50.0% / 5.3% | 64.1% |
| eval A(전체 발췌) | 8 | 8 | 40 | 2 | 2 | 0 | 0 | 2 | 2/7 | 1/1 | 39.1% / 8.7% | 53.6% |
| eval B(좁은 발췌) | 8 | 8 | 37 | 2 | 1 | 1 | 1\* | 3 | 0/7 | 1/1 | 66.7% / 0.0% | 90.9% |
| dev | 4 | 4 | 20 | 2 | 0 | 2 | 1(검증기 GAAP) | 0 | 0/4 | 0/0 | 60.0% / 6.7% | 50.0% |

\* NBR-B는 원문 대조로 판정한 중대 오류다. 자동 표의 "중대 오류 수용" 칸은 정답표 규칙에 걸린 것만 세므로 0으로 나오고, 표에서는 수동 판정으로 합산했다.

**사례별 기계 수용 주장과 원문 대조** (수용 6건 전부):

| 사례 | 수용 주장 | 대조 |
|---|---|---|
| MPC-A (eval, 핵심) | net income attributable to MPC · second quarter of 2026: $5.1 billion / $17.73 per diluted share | 정답. 설명의 '전년 동기 대비 증가'는 같은 블록 다음 문장에 있다(인용 문장 밖). 45Z 세액공제·crack spread 같은 반대 근거는 수용되지 않았다 |
| PBF-A (eval, 핵심) | net income attributable to PBF Energy Inc. · second quarter 2026: $906.4 million | 정답(귀속 순이익과 연결 순이익을 올바로 구분). 비현금 특별 이익 $159.8M(보험 회수 등) 한계 문장은 거부되어, 카드에는 '일회성 포함' 경고가 빠진다 |
| AXTI-B (eval) | CEO 발언 해석(설비·공급망 투자, 수요 대응) | 정답(인용 그대로, 해석 표기) |
| NBR-B (eval) | 매출 · quarter ended June 30, 2025: $63 million, 주체 issuer | **틀림(중대)**. 매각된 Quail Tools의 전년 분기 매출이 회사 매출처럼 제목에 나온다. 검증기가 놓쳤다 → 알려진 누락 테스트로 남겼다(아래 5절) |
| AMCX-B (dev) | operating income $16 million | 수치는 맞다. 그러나 **v4 검증기가 GAAP 영업이익을 non-GAAP으로 채웠다** → v5에서 수정했다 |
| AMCX-B (dev) | 광고 매출 해석 | 틀림. "mid-single digit"을 "중단수위"로 옮긴 알아볼 수 없는 한국어다 |

**안정성 반복 4사례**(PBF-B, MPC-B, DK-B, NBR-A): 4건 모두 응답 텍스트가 첫 실행과 **완전히 같았다**(temperature 0, seed 고정). 새 중대 오류는 없었다.

**거부 91건의 원인**(현재 검증기로 재계산): 대부분 모델이 프롬프트 규칙을 지키지 못한 것이다.

| 원인 | 건수 | 분류 |
|---|---|---|
| metric을 식별자 형태로 씀(`net_income`, `gross_margin`) → 인용에 없음 | 22 | 모델 형식 오류 |
| 한국어 설명에 숫자·연도 사용("2026 년 2 분기", "9%") | 16 | 모델 규칙 위반 |
| 블록에 없는 기간을 문맥에서 채움(unknown 대신) | 13 | 모델 규칙 위반 |
| 비교 문장의 과거 값까지 figures에 넣음, 범위 문구 변형 | 15+3 | 모델 규칙 위반 |
| 인용 변형·절단 | 7 | 모델 오류(1건은 글머리 기호만 바뀜 `◦`→`•`, dev) |
| 머리글 없는 표 행 | 5 | 검증기 설계상 거부(표 파서 보류 범위) |
| 숫자 구절 절단, 기타 | 7 | 모델 오류 |

**검증기 과잉 거부로 보이는 사례**(2건, 모두 dev, 수정하지 않았다):

1. 글머리 기호만 다른 인용 거부(AMCX-A)
2. "Effective backlog, including bookings since …, is $100.6 million"에서 수치에 가장 가까운 'bookings'를 다른 지표로 봐서 거부(AEHR-A)

정상 실행 직전에 검증을 완화하지 않기 위해 기록만 했다.

**중요 사실 누락의 분리**:

- 모델에 보이지 않아 놓친 것(발췌 문제): B군 8건. B군은 좁은 발췌라 입력 밖 사실이 있다. A군은 0건이다.
- 보고도 놓친 것: 모델 단계에서 입력 내 중요 사실의 50%는 주장으로 냈지만, 규칙 위반으로 거부되어 최종 회수는 5.3%에 그쳤다.
- 빈 답은 0건이다. 모든 사례에서 3~5개 주장을 냈다.

**생성됐지만 검증기가 막은 중대 오류**(eval 5건):

- AXTI 전 분기·전년 매출을 현재 값으로 포함(2건)
- CORT 한 제품 매출을 총매출로 씀
- MPC 자회사 MPLX 배당 성장률을 MPC 자체 수치로 씀
- PBF 귀속 순이익 수치를 연결 순이익에 붙임

dev에서는 AEHR 전년 분기 매출을 현재 값으로 포함한 1건이 더 있었다. 검증기가 이 모델의 전형적 오류를 대부분 막았지만, 주체 오류 1건(NBR-B)은 통과시켰다.

## 4. 채택 기준 대비 (eval, 작은 표본에 한정)

| 기준 | 결과 | 판정 |
|---|---|---|
| 기계 검증을 통과한 중대 오류 0 | 1 (NBR-B) | 미달 |
| JSON/schema 성공률 90% 이상 | 100% (16/16) | 충족 |
| 수용 주장 정확도 95% 이상 | 75% (3/4, 분모 작음) | 미달 |
| 입력 내 중요 근거 회수율 70% 이상 | 수용 기준 5.3%(모델 단계 50%) | 미달 |
| warm p95 120초 이내 | 21.2초 | 충족 |
| 안정성 반복에서 새 중대 오류 없음 | 없음, 4/4 동일 응답 | 충족 |

**최종 판정: 현재 보류.** 속도·형식·재현성은 좋다. 하지만 이 프롬프트와 검증기 조합에서는 쓸 수 있는 초안이 14개 중 2개뿐이고, 중대 오류 1건이 통과했다.

좁은 범위(예: 규칙을 단순화한 수치 추출만, 또는 번역)로 다시 시험할 수는 있다. 그 경우 이번 결과를 보고 프롬프트를 바꾸는 **새 실험**으로 분리해야 하고, 이번 eval 결과를 일반화 성능으로 쓰지 않는다. 운영 연결·자동 추천·후보 탈락 판단은 구현하지 않았다.

## 5. 이번 시험에서 나온 코드 변경

- **context-check-v5**(5149743): 문장에 'Adjusted'가 어디든 있으면 GAAP 영업이익을 non-GAAP으로 채우던 v4 결함을 고쳤다.
  - 새 기준: 지표 이름, 또는 수치에 가장 가까운 지표 언급 바로 앞의 GAAP/non-GAAP 표기로 판단한다. 없으면 unknown이다.
  - 더 엄격해지는 방향이다. 발견 사례는 dev(AMCX-B)다.
  - 저장된 로컬 응답 20건을 v5로 오프라인 재검증한 결과, 이 GAAP 표기 1건 외에는 수용·거부가 바뀌지 않았다.
  - 운영 일간 context 단계 버전도 context-v5로 올렸다. 9/27 정상 실행이 v5 초안의 첫 운영이 된다.
- **알려진 누락**: NBR-B(매각 사업부 매출을 회사 매출로 표기)는 eval 사례라 고치지 않았다. `test_known_miss_divested_unit_revenue_as_issuer`에 expectedFailure로 남겼고, 검증기가 이를 잡게 되면 테스트가 통과로 바뀐다.
- 채점에 GAAP 표기 불일치 검사를 추가했다. 정답표에 미리 적어 둔 gaap 값과 비교한다.

## 6. 운영 불변 확인

- 시험 중 Gemini·SEC·Telegram 요청, 메시지 발송, 추적 등록은 없었다.
- 로컬 `data/processed`·`config`에 쓰지 않았다. 도구는 두 경로로의 출력을 거부하고, 테스트가 이를 확인한다.
- 원문은 고정 사본만 읽었다.
- 작업 트리의 운영 원장 파일은 변경 없음(git status).
- 도구는 `.env`와 키를 읽지 않는다. `run_sources`/`run_drafts`/`store_context`를 부르면 실패하도록 한 테스트가 통과한다.

## 7. 미검증·다음

- **Gemini 비교**: 9/27 정상 실행이 AXTI, MPC, CORT, RPAY, NBR 초안을 만들면 J1 감사 사본으로 비교할 수 있다. 같은 문서·블록·프롬프트·대상 회계연도라면 A군 사례와 paired 비교가 된다(프롬프트 버전은 동일). 그때 v5로 두 출력을 함께 재검증해 이 표에 합친다.
- 번역 성능, 다른 모델, 다른 발췌 전략은 시험하지 않았다.
