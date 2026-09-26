"""Isolated context verification; no Telegram credentials or delivery paths."""
import hashlib
import os
import subprocess
import sys
import common as c


PROTECTED = ("candidate_alerts.json", "notify_state.json", "command_queue.json", "telegram_offset.json",
             "daily_runs.json")
# A cache-only run must not spend or record any SEC/model request, nor rewrite a stored observation.
CACHE_ONLY = ("model_budget.json", "candidate_context_state.json")


def fingerprints(cache_only: bool = False):
    paths = [c.DATA_DIR / name for name in PROTECTED]
    paths += [c.csv_path("investment_review_log"), c.csv_path("review_history")]
    if cache_only:
        paths += [c.DATA_DIR / name for name in CACHE_ONLY]
        paths += sorted((c.DATA_DIR / "candidate_observations").glob("OB-*.json"))
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None for p in paths}


def main():
    if os.environ.get("RESEARCH_DISABLE_SEND") != "1":
        raise ValueError("verification requires delivery disabled")
    if os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_CHAT_ID"):
        raise ValueError("verification must not receive Telegram credentials")
    import candidates
    import candidate_context as context
    cache_only = os.environ.get("VERIFY_CACHE_ONLY") == "true"
    refresh = os.environ.get("VERIFY_REFRESH_SCREEN") == "true"
    if cache_only and refresh:
        raise ValueError("cache-only and screen refresh are mutually exclusive")
    before = fingerprints(cache_only)
    code = 0
    try:
        if not cache_only:
            if refresh:
                subprocess.run([sys.executable, "scripts/screen_revisions.py"], cwd=c.ROOT, check=True)
            code = context.main([])
        candidates.generate(translate_now=False)
        after = fingerprints(cache_only)
        changed = [p for p in before if after.get(p) != before[p]]
        if changed:
            print(f"[verify] changed: {changed}")
            raise ValueError("verification changed protected state")
        c.record_run("context_verification", "failed" if code else "success",
                     cache_only=cache_only, screen_refreshed=refresh, protected_state_unchanged=True)
    except Exception as error:
        c.record_run("context_verification", "failed", error_type=type(error).__name__)
        raise
    return code


if __name__ == "__main__":
    raise SystemExit(main())
