"""L4: stage-by-stage offline evaluation of the 36 production audits (9/29-10/4). No network.

python l4_eval.py <scratchpad> <out_dir>    (run from the repository root)
"""
import copy
import gzip
import hashlib
import importlib.util
import json
import pathlib
import sys
from collections import Counter

SP, OUT = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
sys.path.insert(0, "scripts")
import candidates as k  # noqa: E402

RUNS = {"36528079469": "2026-09-29", "36674489444": "2026-09-30", "36822997450": "2026-10-01",
        "36880974655": "2026-10-02", "37099766046": "2026-10-03", "37181539693": "2026-10-04"}


def load_stage(name, path):
    spec = importlib.util.spec_from_file_location(f"stage_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audits = []
if (SP / "art").is_dir():  # the downloaded Actions artifacts
    for run, day in RUNS.items():
        for f in sorted((SP / "art" / run / "context_audit" / day).glob("*.json")):
            raw = f.read_bytes()
            audits.append({"run": run, "day": day, "file": f.name, "sha256": hashlib.sha256(raw).hexdigest(),
                           "record": json.loads(raw)})
else:  # the kept copy: python data/eval/l4_2026-10-04/l4_eval.py data/eval/l4_2026-10-04 <out_dir>
    with gzip.open(SP / "audits.json.gz", "rt", encoding="utf-8") as h:
        records = json.load(h)
    listed = json.loads((SP / "manifest.json").read_text(encoding="utf-8"))
    for row, record in zip(listed, records):
        audits.append({"run": row["run_id"].split("-")[0], "day": row["kst_day"], "file": row["file"],
                       "sha256": row["sha256"], "record": record})
assert len(audits) == 36, len(audits)
OUT.mkdir(parents=True, exist_ok=True)
manifest = [{"run_id": a["run"] + "-1", "kst_day": a["day"], "file": a["file"], "sha256": a["sha256"],
             "ticker": a["record"]["ticker"], "outcome": a["record"]["outcome"],
             "parser_version": a["record"]["parser_version"]} for a in audits]
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
with gzip.open(OUT / "audits.json.gz", "wt", encoding="utf-8") as h:  # fixed input; artifacts expire 10/29-11/03
    json.dump([a["record"] for a in audits], h, ensure_ascii=False)

stage_dir = SP / "stages" if (SP / "stages").is_dir() else SP / "stage_validators"
stages = {"S0_v7": stage_dir / "s0_v7.py", "S1_goodwill": stage_dir / "s1_goodwill.py",
          "S2_L1": stage_dir / "s2_l1.py", "S3_L1L2": stage_dir / "s3_l1l2.py"}
v8 = load_stage("v8_detector", stages["S3_L1L2"])
answered = [a for a in audits if isinstance(a["record"].get("answer"), dict)]
results, previous = {}, None
for name, path in stages.items():
    ctx = load_stage(name, path)
    per = []
    for a in answered:
        r = a["record"]
        v = ctx.validate_draft(copy.deepcopy(r["answer"]), r["blocks"], r["issuer"])
        per.append({"ticker": r["ticker"], "day": a["day"], "status": v["context_status"],
                    "claims": v["claims"], "limitations": v["limitations"],
                    "rejected": [x["reason"] for x in v["rejected"]]})
    accepted = [(p["ticker"], p["day"], what, x) for p in per for what in ("claims", "limitations") for x in p[what]]
    role_errors = [(t, x["text_ko"]) for t, _, _, x in accepted
                   if v8.role_problem(str(x.get("metric") or ""), x["figures"], x["quote"])[0]]
    keys = {(t, d, x["quote"], tuple(x["figures"])) for t, d, _, x in accepted}
    new = sorted(keys - previous["keys"]) if previous else []
    gone = sorted(previous["keys"] - keys) if previous else []
    limits = [x for _, _, what, x in accepted if what == "limitations"]
    ranks = Counter(rank for rank, _ in k.limitation_order(limits))
    results[name] = {
        "drafts": len(per), "accepted_claims": sum(len(p["claims"]) for p in per),
        "accepted_limitations": len(limits),
        "core_fact_guidance": sum(1 for p in per for x in p["claims"] if x["core"] and x["kind"] in ("fact", "guidance")),
        "core_any_kind": sum(1 for p in per for x in p["claims"] if x["core"]),
        "draft_ready": sum(p["status"] == "draft_ready" for p in per),
        "statuses": dict(Counter(p["status"] for p in per)),
        "rejected": dict(Counter(r for p in per for r in p["rejected"]).most_common()),
        "change_or_effect_shown_as_level": role_errors,
        "limitation_rank": {"one_off": ranks.get(0, 0), "specific": ranks.get(1, 0), "disclaimer": ranks.get(2, 0)},
        "new_vs_previous": [{"ticker": t, "day": d, "text_ko": next(x["text_ko"] for tt, dd, _, x in accepted
                                                                   if (tt, dd, x["quote"], tuple(x["figures"])) == (t, d, q, f))}
                            for t, d, q, f in new],
        "gone_vs_previous": [{"ticker": t, "day": d, "quote": q[:120], "figures": list(f)} for t, d, q, f in gone],
    }
    previous = {"keys": keys, "per": per}
    if name == "S3_L1L2":
        final = per

# S4: what the card shows (L3) from the S3 result, against the v7 first-3 / first-2 display.
cards = []
for p in final:
    if not p["claims"] and not p["limitations"]:
        continue
    shown = [x["text_ko"] for x in k.stated_order(p["claims"])[:3]]
    old = [x["text_ko"] for x in p["claims"] if x["kind"] in ("fact", "guidance")][:3]
    lims = [(rank, x["text_ko"]) for rank, x in k.limitation_order(p["limitations"])[:2]]
    cards.append({"ticker": p["ticker"], "day": p["day"], "status": p["status"], "facts_shown": shown,
                  "facts_first3_before": old, "limitations_shown": lims})
results["S4_L3_cards"] = {"cards": len(cards), "changed_fact_selection": sum(c["facts_shown"] != c["facts_first3_before"] for c in cards),
                          "detail": cards}
results["inputs"] = {"audits": len(audits), "answered": len(answered), "failed": len(audits) - len(answered),
                     "failed_reasons": dict(Counter(json.dumps(a["record"].get("error"), sort_keys=True)
                                                    for a in audits if a not in answered))}
(OUT / "stages.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
for name in stages:
    r = results[name]
    print(name, {x: r[x] for x in ("accepted_claims", "accepted_limitations", "core_fact_guidance", "core_any_kind",
                                   "draft_ready", "limitation_rank")}, "role_errors", len(r["change_or_effect_shown_as_level"]),
          "new", len(r["new_vs_previous"]), "gone", len(r["gone_vs_previous"]))
print("S4", {x: results["S4_L3_cards"][x] for x in ("cards", "changed_fact_selection")}, results["inputs"])
