# I3 오프라인 재검증 표

생성: `python tests/offline_revalidation.py`. 모델·SEC 요청 없음, 운영 자료 읽기만 함. 현재 검증기 context-check-v4. 이 결과를 운영 초안으로 저장하거나 과거 날짜로 소급하지 않는다.

## 1. 실제 출력 fixture (RealOutputTest, run 36247419404의 실제 출력을 옮긴 구조화 항목)

fixture는 실제 출력의 문장·수치를 옮기고 v3 필드(metric/period/kind)를 채운 시험 입력이다. 모델이 v3 프롬프트로 같은 필드를 낼지는 이 표가 보여 주지 않는다(fixture 범위만 검증).

| 사례 | v2 결과 | 현재 검증기 결과 | 거부 사유 | 핵심 여부 | 기대와 |
|---|---|---|---|---|---|
| AMCX 영업이익 두 지표 — 영업이익 $16 million | multiple_statements_for_figures | 수용 | - | False | 일치 |
| AMCX 조정 영업이익 $46 million | unsupported_metric | 수용 | - | False | 일치 |
| AMCX 지표-수치 뒤바뀜(영업이익에 $46 million) | (모의 오류) | 거부 | figure_belongs_to_another_metric | - | 일치 |
| AEHR 회계연도 매출 전망 범위 | unsupported_metric | 수용 | - | True | 일치 |
| TALO 생산량 전망 64 to 68 MBo/d | figure_not_verbatim | 수용 | - | True | 일치 |
| DK 머리글 없는 표 행 169.5 | unsupported_metric | 거부 | ambiguous_table_figures | - | 일치 |
| PBF 순이익을 $906.4 million으로 제시(원문 $915.0 million) | number_or_unit_in_note | 거부 | figure_not_verbatim | - | 일치 |
| PBF 순이익 $915.0 million(원문 그대로) | (대조용) | 수용 | - | True | 일치 |
| PBF 실제 전체 문장: 순이익 ↔ $906.4 million(귀속 순이익의 수치) | number_or_unit_in_note | 거부 | figure_belongs_to_another_metric | - | 일치 |
| PBF 실제 전체 문장: 귀속 순이익 ↔ $915.0 million(연결 순이익의 수치, v3는 수용·v4 거부) | (모의 오류) | 거부 | figure_belongs_to_another_metric | - | 일치 |
| PBF 실제 전체 문장: 귀속 순이익 ↔ $906.4 million | (대조용) | 수용 | - | True | 일치 |
| 배당 문법 괄호 ($0.255 per share) | figure_not_verbatim | 수용 | - | False | 일치 |
| 숫자 구절을 자른 수치 '$5' | (모의 오류) | 거부 | figure_cut_from_source | - | 일치 |

## 2. 저장된 v2 초안의 거부 문장 32건 (부분 재검증)

저장본은 거부 문장의 요약(문장·수치·인용 200자·위치)만 남아 있다. metric/period/kind/gaap가 없어 그 검사는 다시 하지 않았다. 인용이 200자에서 잘린 경우 수치 구간은 원문 블록 전체와 대조했다.

| CTX | 종류 | v2 사유 | 원문 위치 | 인용 잘림 | 수치 구간(현재) | 표 행 | 설명문 수치 | 판정 |
|---|---|---|---|---|---|---|---|---|
| 117FF656 | claim | multiple_statements_for_figures | 있음 | 아니오 | $16 million: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 117FF656 | claim | unsupported_metric | 있음 | 아니오 | $46 million: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 117FF656 | claim | unsupported_metric | 있음 | 아니오 | $547 million: 통과; 9%: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 117FF656 | claim | figure_not_verbatim | 있음 | 아니오 | $200 million to $225 million: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 117FF656 | limitation | unsupported_metric | 있음 | 예 | - | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 117FF656 | limitation | unsupported_metric | 있음 | 예 | - | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 7E739AC1 | claim | figure_not_verbatim | 있음 | 예 | 68.6 thousand barrels of oil per day: 통과; 93.7 thousand barrels of oil equivalent : 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 7E739AC1 | claim | period_not_in_source | 있음 | 아니오 | $402.4 million: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 7E739AC1 | claim | figure_not_verbatim | 있음 | 예 | 66 MBo/d: 통과; 89 MBoe/d: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 7E739AC1 | claim | figure_not_verbatim | 있음 | 아니오 | $18.25 per Boe: 통과; $1.75 per Boe: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 7E739AC1 | claim | figure_not_verbatim | 있음 | 예 | 64 to 68 MBo/d: 통과; 87 to 91 MBoe/d: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 7E739AC1 | limitation | figure_not_verbatim | 있음 | 아니오 | $1.75 per Boe: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 7E739AC1 | limitation | unsupported_metric | 있음 | 아니오 | - | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 7E739AC1 | limitation | gaap_not_as_stated | 있음 | 예 | - | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 8222B965 | claim | number_or_unit_in_note | 있음 | 아니오 | $906.4 million: 통과; $7.54 per share: 통과 | 아니오 | 수치·단위 포함 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 8222B965 | claim | figure_not_verbatim | 있음 | 아니오 | $5.2 million: 통과; $(0.05) per share: 통과 | 아니오 | 수치·단위 포함 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 8222B965 | claim | number_or_unit_in_note | 있음 | 예 | $753.1 million: 통과; $6.22 per share: 통과 | 아니오 | 수치·단위 포함 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 8222B965 | claim | figure_not_verbatim | 있음 | 예 | $118.5 million: 통과; $(1.03) per share: 통과 | 아니오 | 수치·단위 포함 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 8222B965 | claim | number_or_unit_in_note | 있음 | 예 | $250.0 million: 통과; $356.5 million: 통과 | 아니오 | 수치·단위 포함 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| 8222B965 | limitation | number_or_unit_in_note | 있음 | 예 | $159.8 million: 통과; $1.32 per share: 통과 | 아니오 | 수치·단위 포함 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| A0639925 | claim | unsupported_metric | 있음 | 아니오 | $130 million: 통과; $150 million: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| A0639925 | claim | figure_not_verbatim | 있음 | 아니오 | 160%-200%: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| A0639925 | claim | unsupported_metric | 있음 | 아니오 | 18%: 통과; 22%: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| A0639925 | claim | unsupported_metric | 있음 | 아니오 | $100.6 million: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| A0639925 | claim | unsupported_metric | 있음 | 아니오 | $18.8 million: 통과; $14.1 million: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| CFFAC44D | claim | unsupported_metric | 있음 | 아니오 | 169.5: 통과; 10.6: 통과; 180.1: 통과 | 예 | 통과 | 현재 검증기에서도 거부(머리글 없는 표 행) |
| CFFAC44D | claim | figure_not_verbatim | 있음 | 아니오 | $0.255 per share: 통과; (15.6): 통과 | 예 | 통과 | 현재 검증기에서도 거부(머리글 없는 표 행) |
| CFFAC44D | claim | unsupported_metric | 있음 | 아니오 | (442,893): 통과; (7.2): 통과; (12.8): 통과; (20.0): 통과 | 예 | 통과 | 현재 검증기에서도 거부(머리글 없는 표 행) |
| CFFAC44D | claim | unsupported_metric | 있음 | 아니오 | $56.7 million: 통과; $76.6 million: 통과; $19.9 million: 통과; 26.0%: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| CFFAC44D | claim | unsupported_metric | 있음 | 예 | $100.7 million: 통과; $138.1 million: 통과; $37.4 million: 통과; 27.1%: 통과 | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| CFFAC44D | limitation | unsupported_metric | 있음 | 예 | - | 아니오 | 통과 | 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 |
| CFFAC44D | limitation | quote_not_in_block | 없음 | 예 | - | 아니오 | 통과 | 현재 검증기에서도 거부(원문 위치 불일치) |

판정 집계: 수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증 28건, 현재 검증기에서도 거부(머리글 없는 표 행) 3건, 현재 검증기에서도 거부(원문 위치 불일치) 1건
