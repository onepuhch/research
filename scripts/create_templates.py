"""reports/templates 폴더에 마크다운 리포트 템플릿을 생성한다.

사용법:
    python scripts/create_templates.py            # 없는 것만 생성
    python scripts/create_templates.py --overwrite  # 기존 것도 덮어쓰기
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

REPORT_TEMPLATE_DIR = c.ROOT / "reports" / "templates"


TEMPLATES = {
    "daily_signal_template.md": """# 일일 시그널 점검

## 오늘의 핵심 변화
- 섹터/테마:
- 변한 숫자(이전 → 현재):
- 출처:
- 투자 판단에 미치는 영향:

## 선행지표
- 가격/ASP:
- 수주/리드타임:
- 재고/가동률:
- 공급망/CAPEX:
- 이익 추정치/EPS(컨센서스 방향):

## 병목 후보
- 밸류체인:
- 병목 후보:
- 순수 플레이어:
- 시장이 덜 보는 이유:
- 추가 확인:

## 액션
- 관찰 유지:
- 추가 리서치:
- 비중 조절(증액/축소/제외):
""",
    "weekly_research_brief_template.md": """# 주간 리서치 브리프

## 이번 주 결론
- 가장 강해진 아이디어:
- 약해진 아이디어:
- 새로 추가할 섹터/밸류체인:

## 업종별 핵심 지표 변화
| 업종 | 선행지표 변화 | EPS/이익 추정치 변화 | 밸류에이션 변화 | 판단 |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## 병목 후보 업데이트
| 테마 | 밸류체인 | 병목 후보 | 근거 | 다음 액션 |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## 컨센서스 대비 내 엣지
| 아이디어 | 시장 컨센서스 | 내 견해 | 격차를 닫을 촉매 | 확신도 |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## 리스크와 반증(정량 종료조건)
- 핵심 지표 둔화 기준:
- CAPEX/공급 증가 기준:
- 고객 재고 기준:
- 밸류에이션 과열 기준:

## 다음 주 확인할 데이터
-
""",
    "monthly_sector_map_template.md": """# 월간 섹터 맵

## 섹터 우선순위 (확신도/단계 기준)
| 순위 | 섹터/업종 | 현재 단계 | 핵심 이익 변수 | 선행지표 | 확신도 | 판단 |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |

## 밸류체인별 병목 지도
| 메인 테마 | 밸류체인 | 병목 후보 | 순수 플레이어 | 시장 미반영 포인트 |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## 이익 추정치와 밸류에이션
- EPS 상향이 강한 구간:
- 가격 상승률보다 EPS 상향률이 큰 후보:
- PER 착시 위험 후보:

## 포지션 점검
- 증액 후보(숫자로 강화 중):
- 축소 후보(지표 둔화):
- 제외(종료조건 발생):

## 프레임 수정 기록
- 새로 추가할 변수:
- 기존 체크리스트의 한계:
""",
    "quarterly_earnings_review_template.md": """# 분기 실적 리뷰

## 분기 핵심 결론
- 실적이 투자 가설을 강화한 부분:
- 실적이 투자 가설을 약화한 부분:
- 컨센서스/EPS 변화:

## 실적 체크
| 종목/업종 | 매출 | 영업이익 | EPS | 가이던스 | 시장 반응 | 판단 |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |

## 선행지표 재점검
- ASP/가격:
- 수주/백로그:
- 재고:
- CAPEX:
- 고객 수요:

## 보유/축소/종료 판단
- 보유 조건 충족 여부:
- 종료 조건(정량) 발생 여부:
- 다음 분기 확인할 지표:

## 복기 (유형별 적중률 갱신)
- 맞은 점:
- 틀린 점:
- 프레임 수정:
""",
}


def write_templates(overwrite: bool) -> list[Path]:
    REPORT_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, content in TEMPLATES.items():
        path = REPORT_TEMPLATE_DIR / filename
        if path.exists() and not overwrite:
            continue
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str]) -> int:
    overwrite = "--overwrite" in argv
    written = write_templates(overwrite=overwrite)
    if written:
        print("생성된 템플릿:")
        for path in written:
            print(f"- {path}")
    else:
        print("템플릿이 이미 있습니다. 다시 만들려면 --overwrite 를 쓰세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
