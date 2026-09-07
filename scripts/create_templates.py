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


TEMPLATES = {'daily_signal_template.md': '# 일일 신호 검토\n'
                             '\n'
                             '| ID / 기업 | 사건: 계획·계약·실현 | 확인한 사실 | 원문 URL·인용·발표일 | 해석과 한계 |\n'
                             '| --- | --- | --- | --- | --- |\n'
                             '| | | | | |\n'
                             '\n'
                             '## 기존 가설에 미치는 변화\n'
                             '- 기업 식별자 / thesis_key / idea_id:\n'
                             '- 판단 변화: 강화·유지·약화·자료 부족\n'
                             '- 반증 근거와 다음 점검일:\n'
                             '- 신규 등록 또는 기존 가설 근거 연결:\n',
 'weekly_research_brief_template.md': '# 주간 판단 변화\n'
                                      '\n'
                                      '| idea_id | 사업 단계 | 근거 수준 | 검토 상태 | 이전 → 현재 판단 | 변경 사유·근거 '
                                      'ID | 다음 점검 |\n'
                                      '| --- | --- | --- | --- | --- | --- | --- |\n'
                                      '| | | | | | | |\n'
                                      '\n'
                                      '## 숫자 점검\n'
                                      '- 같은 FY·출처·통화·단위·회계기준의 컨센서스 변화:\n'
                                      '- 실적·회사 전망 (컨센서스와 별도):\n'
                                      '- 부족하거나 오래된 관측:\n'
                                      '- 반증 규칙 발동 / 자료 부족:\n'
                                      '\n'
                                      '## 연구 품질\n'
                                      '- 원문 정확도·검토 가치·예측 결과의 구분:\n'
                                      '- 평가한 표본과 미확인 표본 수:\n'
                                      '- 운영 실패·다음 확인 자료:\n',
 'monthly_sector_map_template.md': '# 월간 병목 연구 지도\n'
                                   '\n'
                                   '| 노드 | 수요 근거 | 공급 제약 | 수혜 경로 | 독립 반증 근거 | 병목 해소 조건 | 관련 '
                                   'idea_id |\n'
                                   '| --- | --- | --- | --- | --- | --- | --- |\n'
                                   '| | | | | | | |\n'
                                   '\n'
                                   '## 가설 변화\n'
                                   '- 강화·약화·종료 가설과 이유:\n'
                                   '- 사업 단계와 근거 수준:\n'
                                   '- 새로 확인할 이익 변수와 출처:\n'
                                   '- 동일 날짜 EPS·가격 baseline 유무 (PER 변화만으로 저평가 판정 금지):\n',
 'quarterly_earnings_review_template.md': '# 분기 실적 검토\n'
                                          '\n'
                                          '| 기업 | 기간 말 | 발표일 | 관측일 | actual / guidance / consensus '
                                          '| 지표·단위·회계기준 | 수치 | 출처 |\n'
                                          '| --- | --- | --- | --- | --- | --- | --- | --- |\n'
                                          '| | | | | | | | |\n'
                                          '\n'
                                          '## 가설 대조\n'
                                          '- 사전에 등록한 조건과 실제 결과:\n'
                                          '- 소급 대조 여부:\n'
                                          '- 강화·약화 근거 / 독립 반증:\n'
                                          '- GAAP·non-GAAP 차이와 확인 필요 사항:\n'
                                          '- 같은 FY 컨센서스 이력 유무:\n'
                                          '- 판단 변경 사유·다음 점검일:\n'}


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
