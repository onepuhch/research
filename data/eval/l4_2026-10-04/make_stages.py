"""Build the stage validators for L4 from the v7 (6d4211d) and v8 (HEAD) files (scratch only)."""
import pathlib

d = pathlib.Path(__file__).parent / "stages"


def rep(s, old, new):
    assert s.count(old) == 1, old
    return s.replace(old, new)


v7 = (d / "s0_v7.py").read_text(encoding="utf-8")
# S1: v7 plus Codex's goodwill patch only (as in the stash, before L1).
s1 = rep(v7, 'FORWARD = ("expect", "outlook", "guidance", "forecast", "anticipate", "project", "will ", "target")',
         'FORWARD = ("expect", "outlook", "guidance", "forecast", "anticipate", "project", "target")')
s1 = rep(s1, "def check_item(item: dict, blocks: dict, issuer: dict, what: str)",
         "def has_forward_wording(quote: str) -> bool:\n"
         "    return any(word in quote for word in FORWARD) or bool(re.search(r\"\\bwill\\b\", quote))\n\n\n"
         "def check_item(item: dict, blocks: dict, issuer: dict, what: str)")
s1 = rep(s1, 'if kind == "fact" and any(w in quote for w in FORWARD):', 'if kind == "fact" and has_forward_wording(quote):')
s1 = rep(s1, 'if kind == "guidance" and not any(w in quote for w in FORWARD):',
         'if kind == "guidance" and not has_forward_wording(quote):')
(d / "s1_goodwill.py").write_text(s1, encoding="utf-8")

v8 = (d / "s3_l1l2.py").read_text(encoding="utf-8")
# S2: v8 with the L2 changes turned back to v7 behaviour.
s2 = rep(v8, "and not repeated_name(q, m, name, s, claimed):", ":")
s2 = rep(s2, "        if RATE.search(squash(figure)):\n            # '45.0 percent of revenue'",
         "        if False:\n            # '45.0 percent of revenue'")
s2 = rep(s2, 'if squash(gaap) == "adjusted" and expected == "non-GAAP":', "if False:")
s2 = rep(s2, 'if what == "claim" and item.get("direction", "unknown") not in DIRECTIONS:',
         'if what == "claim" and (item.get("direction", "unknown") not in DIRECTIONS\n'
         '                            or not set(item.get("drivers") or ["unknown"]) <= set(DRIVERS)):')
s2 = rep(s2, 'RAISE = re.compile(r"\\b(?:rais(?:e|es|ed|ing)|increas(?:e|es|ed|ing)|higher|above|up from|improv\\w*)\\b")',
         'RAISE = re.compile("raise|raised|increase|increased|higher|above|up from|improv")')
s2 = rep(s2, 'LOWER = re.compile(r"\\b(?:lower(?:s|ed|ing)?|reduc(?:e|es|ed|ing)|cut(?:s|ting)?|decreas(?:e|es|ed|ing)|below|"\n'
             '                   r"down from|declin\\w*)\\b")',
         'LOWER = re.compile("lower|lowered|reduce|reduced|cut|decrease|decreased|below|down from|declin")')
(d / "s2_l1.py").write_text(s2, encoding="utf-8")
print("stages written")
