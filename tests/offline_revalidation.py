"""I3: re-check stored real model outputs against the current validator, offline and read-only.

No model or SEC request, no write. Two parts:
1. The RealOutputTest fixtures (full v3-form items built from verification run 36247419404).
2. Every refused item kept in the stored v2 drafts (CTX-*.json). These keep only an excerpt
   (note, figures, quote cut at 200 chars, block id), not metric/period/kind. Only the checks that
   those fields allow are re-run; nothing missing is reconstructed.

    python tests/offline_revalidation.py > docs/i3_offline_revalidation.md
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
sys.path.insert(0, str(HERE))
import candidate_context as ctx  # noqa: E402
import company_filings as cf  # noqa: E402
from test_h_followup import check  # noqa: E402

PBF = ("The company reported second quarter 2026 net income of $915.0 million and net income attributable "
       "to PBF Energy Inc. of $906.4 million or $7.54 per share.")  # the full first sentence of the stored block
FIXTURES = [
    # (case, previous v2 outcome, quote, issuer, fields, expected)
    ("AMCX 영업이익 두 지표 — 영업이익 $16 million", "multiple_statements_for_figures",
     "•Operating income of $16 million; Adjusted Operating Income(1) of $46 million.",
     {"ticker": "AMCX", "name": "AMC Networks"}, dict(metric="Operating income", figures=["$16 million"]), "수용"),
    ("AMCX 조정 영업이익 $46 million", "unsupported_metric",
     "•Operating income of $16 million; Adjusted Operating Income(1) of $46 million.",
     {"ticker": "AMCX", "name": "AMC Networks"}, dict(metric="Adjusted Operating Income", figures=["$46 million"]), "수용"),
    ("AMCX 지표-수치 뒤바뀜(영업이익에 $46 million)", "(모의 오류)",
     "•Operating income of $16 million; Adjusted Operating Income(1) of $46 million.",
     {"ticker": "AMCX", "name": "AMC Networks"}, dict(metric="Operating income", figures=["$46 million"]), "거부"),
    ("AEHR 회계연도 매출 전망 범위", "unsupported_metric",
     "For the fiscal year ending June 25, 2027, Aehr expects total company revenue to be between $130 million and $150 million",
     {"ticker": "AEHR", "name": "Aehr Test Systems"},
     dict(kind="guidance", metric="total company revenue", figures=["$130 million", "$150 million"],
          period="fiscal year ending June 25, 2027"), "수용"),
    ("TALO 생산량 전망 64 to 68 MBo/d", "figure_not_verbatim",
     "Talos has increased its full-year 2026 production guidance and now expects production to range from 64 to 68 MBo/d and 87 to 91 MBoe/d",
     {"ticker": "TALO", "name": "Talos Energy"},
     dict(kind="guidance", metric="production", figures=["64 to 68 MBo/d"], period="full-year 2026", currency=None,
          note_ko="연간 생산량 전망 범위를 높였습니다."), "수용"),
    ("DK 머리글 없는 표 행 169.5", "unsupported_metric",
     "Net income (loss) ; — ; — ; — ; — ; 169.5 ; — ; — ; 10.6 ; 180.1", None,
     dict(metric="Net income", figures=["169.5"], currency=None), "거부"),
    ("PBF 순이익을 $906.4 million으로 제시(원문 $915.0 million)", "number_or_unit_in_note",
     "The company reported second quarter 2026 net income of $915.0 million.", None,
     dict(metric="net income", figures=["$906.4 million"], period="second quarter 2026"), "거부"),
    ("PBF 순이익 $915.0 million(원문 그대로)", "(대조용)",
     "The company reported second quarter 2026 net income of $915.0 million.", None,
     dict(metric="net income", figures=["$915.0 million"], period="second quarter 2026"), "수용"),
    ("PBF 실제 전체 문장: 순이익 ↔ $906.4 million(귀속 순이익의 수치)", "number_or_unit_in_note", PBF,
     {"ticker": "PBF", "name": "PBF Energy"},
     dict(metric="net income", figures=["$906.4 million"], period="second quarter 2026"), "거부"),
    ("PBF 실제 전체 문장: 귀속 순이익 ↔ $915.0 million(연결 순이익의 수치, v3는 수용·v4 거부)", "(모의 오류)", PBF,
     {"ticker": "PBF", "name": "PBF Energy"},
     dict(metric="net income attributable to PBF Energy Inc.", figures=["$915.0 million"],
          period="second quarter 2026"), "거부"),
    ("PBF 실제 전체 문장: 귀속 순이익 ↔ $906.4 million", "(대조용)", PBF,
     {"ticker": "PBF", "name": "PBF Energy"},
     dict(metric="net income attributable to PBF Energy Inc.", figures=["$906.4 million"],
          period="second quarter 2026"), "수용"),
    ("배당 문법 괄호 ($0.255 per share)", "figure_not_verbatim",
     "Common stock dividends ($0.255 per share) were paid in 2026.", None,
     dict(metric="dividends", figures=["$0.255 per share"], period="2026"), "수용"),
    ("숫자 구절을 자른 수치 '$5'", "(모의 오류)",
     "Revenue was $5 million in 2025.", None, dict(metric="revenue", figures=["$5"], period="2025"), "거부"),
]


def fixture_rows():
    rows = []
    for case, before, quote, issuer, fields, expected in FIXTURES:
        result = check(quote, issuer=issuer, **fields)
        got = "수용" if result["claims"] else "거부"
        reason = result["rejected"][0]["reason"] if result["rejected"] else "-"
        core = result["claims"][0]["core"] if result["claims"] else "-"
        rows.append((case, before, got, reason, core, "일치" if got == expected else "불일치"))
    return rows


def stored_rows():
    """Refused items of stored drafts, re-checked only where the kept excerpt allows."""
    rows = []
    for path in sorted(ctx.history_dir().glob("CTX-*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        issuer = record.get("issuer_cik")
        for item in record.get("rejected") or []:
            document_id, _, block_id = item.get("where", "#").partition("#")
            doc = cf.load_document(document_id) or {}
            block = next((cf.block_text(b) for b in doc.get("blocks") or [] if b.get("id") == block_id), None)
            quote = item.get("quote", "")
            cut = len(quote) >= 200
            if block is None:
                located = "원문 블록 없음"
            else:
                located = "있음" if ctx.squash(quote) in ctx.squash(block) else "없음"
            sentence = quote
            if cut and located == "있음":
                # The kept quote stops at 200 chars: continue it in the source to the end of that sentence.
                text = ctx.squash(block)
                start = text.find(ctx.squash(quote))
                end = text.find(". ", start + len(ctx.squash(quote)))
                sentence = text[start:end + 1 if end >= 0 else len(text)]
            figures = []
            for figure in item.get("figures") or []:
                problem = ctx.figure_problem(figure, sentence)
                figures.append(f"{figure}: {problem or '통과'}")
            table = " ; " in quote or " | " in quote
            note = item.get("note_ko", "")
            note_problem = ("수치·단위 포함" if any(ch.isdigit() for ch in note)
                            or any(w in note.lower() for w in ctx.UNIT_WORDS) else "통과")
            rows.append({"ctx": path.stem, "cid": record.get("candidate_id"), "issuer": issuer,
                         "what": item.get("what"), "v2": item.get("reason"), "located": located,
                         "cut": cut, "figures": figures, "table": table, "note": note_problem,
                         "quote": quote[:90]})
    return rows


def verdict(row):
    if row["located"] != "있음":
        return "현재 검증기에서도 거부(원문 위치 불일치)"
    if row["table"] and row["figures"]:
        return "현재 검증기에서도 거부(머리글 없는 표 행)"
    bad = [f for f in row["figures"] if not f.endswith("통과")]
    if bad:
        return "현재 검증기에서도 거부(수치 구간)"
    return "수치·위치 통과, 지표·기간·종류는 원응답 없음으로 미검증"


def main():
    print("# I3 오프라인 재검증 표\n")
    print("생성: `python tests/offline_revalidation.py`. 모델·SEC 요청 없음, 운영 자료 읽기만 함. "
          f"현재 검증기 {ctx.PARSER_VERSION}. 이 결과를 운영 초안으로 저장하거나 과거 날짜로 소급하지 않는다.\n")
    print("## 1. 실제 출력 fixture (RealOutputTest, run 36247419404의 실제 출력을 옮긴 구조화 항목)\n")
    print("fixture는 실제 출력의 문장·수치를 옮기고 v3 필드(metric/period/kind)를 채운 시험 입력이다. "
          "모델이 v3 프롬프트로 같은 필드를 낼지는 이 표가 보여 주지 않는다(fixture 범위만 검증).\n")
    print("| 사례 | v2 결과 | 현재 검증기 결과 | 거부 사유 | 핵심 여부 | 기대와 |\n|---|---|---|---|---|---|")
    for row in fixture_rows():
        print("| " + " | ".join(str(x) for x in row) + " |")
    rows = stored_rows()
    print(f"\n## 2. 저장된 v2 초안의 거부 문장 {len(rows)}건 (부분 재검증)\n")
    print("저장본은 거부 문장의 요약(문장·수치·인용 200자·위치)만 남아 있다. metric/period/kind/gaap가 없어 "
          "그 검사는 다시 하지 않았다. 인용이 200자에서 잘린 경우 수치 구간은 원문 블록 전체와 대조했다.\n")
    print("| CTX | 종류 | v2 사유 | 원문 위치 | 인용 잘림 | 수치 구간(현재) | 표 행 | 설명문 수치 | 판정 |\n"
          "|---|---|---|---|---|---|---|---|---|")
    for row in rows:
        print(f"| {row['ctx'][4:12]} | {row['what']} | {row['v2']} | {row['located']} | "
              f"{'예' if row['cut'] else '아니오'} | {'; '.join(row['figures']) or '-'} | "
              f"{'예' if row['table'] else '아니오'} | {row['note']} | {verdict(row)} |")
    counts = {}
    for row in rows:
        counts[verdict(row)] = counts.get(verdict(row), 0) + 1
    print("\n판정 집계: " + ", ".join(f"{k} {v}건" for k, v in sorted(counts.items(), key=lambda x: -x[1])))


if __name__ == "__main__":
    main()
