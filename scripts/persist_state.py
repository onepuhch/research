"""Persist only named research state; never stage credentials or arbitrary files."""
import subprocess
from datetime import datetime, timezone
import common as c

# The state area, by path rule (Q0-B): what this writer stages is a subset of it, and a remote commit
# touching any path in it (added, changed, deleted or renamed, even if changed back) is another
# writer's state, so this run's commits are never replayed over it.
STATE_PREFIXES = ('data/archive/pre_v2/', 'data/archive/pre_columns/')
STATE_DOCS = ('docs/data_history.md', 'docs/revision_screen.md', 'docs/candidates.md')


def state_area(path):
    """True for a repository path in the state area: the data directory (data/processed/) and the rest."""
    try:
        data = c.DATA_DIR.relative_to(c.ROOT).as_posix().rstrip('/') + '/'
    except ValueError:
        data = 'data/processed/'
    return path.startswith((data, *STATE_PREFIXES)) or path in STATE_DOCS

STATE_FILES = ['source_state.json', 'seen_sources.json', 'notify_state.json', 'run_status.json', 'daily_runs.json',
               'telegram_offset.json', 'command_queue.json', 'pending_tables.json', 'reddit_watch.csv',
               'model_budget.json', 'candidate_alerts.json', 'candidate_alerts.pre_material.json',
               'discovery_timing.json']


def main(message=None):
    """Commit and push; on failure keep this run's unpushed commits as a bundle in the run's report
    artifact (generated state and model-request counts stay recoverable), then fail."""
    try:
        commit_and_push(message)
    except (subprocess.CalledProcessError, OSError):
        keep_unpushed()
        raise


def keep_unpushed():
    out = c.ROOT / 'reports' / 'generated'
    try:
        out.mkdir(parents=True, exist_ok=True)
        ahead = subprocess.run(['git', 'rev-list', '--count', '@{u}..HEAD'], cwd=c.ROOT, capture_output=True, text=True)
        span = '@{u}..HEAD' if ahead.returncode == 0 else 'HEAD'
        if ahead.returncode == 0 and ahead.stdout.strip() == '0':
            return
        name = f"unpersisted_state_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.bundle"
        subprocess.run(['git', 'bundle', 'create', str(out / name), span], cwd=c.ROOT, capture_output=True)
        print(f'[persist] unpushed state kept in reports/generated/{name}')
    except OSError:
        pass


def commit_and_push(message=None):
    files = [c.csv_path(table) for table in c.TABLES] + [c.DATA_DIR / name for name in STATE_FILES]
    files += list((c.ROOT / 'data' / 'archive' / 'pre_v2').glob('*'))
    files += list((c.ROOT / 'data' / 'archive' / 'pre_columns').glob('*.csv'))
    files += list((c.DATA_DIR / 'research_journal').glob('*.json'))
    files += list((c.DATA_DIR / 'return_history').glob('*.json'))
    files += list((c.DATA_DIR / 'run_history').glob('*.json'))
    files += list((c.DATA_DIR / 'consensus_history').glob('*.json'))
    files += list((c.DATA_DIR / 'revision_screen').glob('*.json.gz'))
    files += list((c.DATA_DIR / 'candidate_history').glob('CV-*.json'))
    files += list((c.DATA_DIR / 'candidate_observations').glob('OB-*.json'))
    files += list((c.DATA_DIR / 'company_documents').glob('DOC-*.json.gz'))
    files += list((c.DATA_DIR / 'candidate_context_history').glob('CTX-*.json'))
    files += list((c.DATA_DIR / 'candidate_review_events').glob('RE-*.json'))
    files += [c.DATA_DIR / 'candidate_context_state.json', c.DATA_DIR / 'sec_issuers.json.gz']
    files += [c.DATA_DIR / 'candidates' / 'index.json', c.DATA_DIR / 'candidate_evidence.json',
              c.DATA_DIR / 'translation_cache.json', c.DATA_DIR / 'translation_rejects.json']
    files += [c.ROOT / 'docs' / 'data_history.md', c.ROOT / 'docs' / 'revision_screen.md',
              c.ROOT / 'docs' / 'candidates.md']
    tracked = set(subprocess.run(['git', 'ls-files', '-z'], cwd=c.ROOT, check=True,
                                 capture_output=True, text=True, encoding='utf-8').stdout.split('\0'))
    # Stage deletion of a recovered journal as well as existing state files.
    paths = [p.relative_to(c.ROOT).as_posix() for p in files
             if p.is_file() or p.relative_to(c.ROOT).as_posix() in tracked]
    outside = [p for p in paths if not state_area(p)]
    if outside:
        raise ValueError(f'state file outside the state area: {outside[:3]}')
    subprocess.run(['git', 'add', '--', *paths], cwd=c.ROOT, check=True)
    if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=c.ROOT).returncode != 0:
        subprocess.run(['git', 'diff', '--cached', '--check'], cwd=c.ROOT, check=True)
        subprocess.run(['git', 'commit', '-m', message or f'chore: research state {c.today()}'], cwd=c.ROOT, check=True)
    # Push even with nothing new staged: an earlier commit may not have reached the remote.
    # On conflict, fail visibly; never force-push a competing writer's state.
    if subprocess.run(['git', 'push'], cwd=c.ROOT).returncode != 0:
        replay_on_remote()
        subprocess.run(['git', 'push'], cwd=c.ROOT, check=True)  # once: a second race fails
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=c.ROOT, check=True, capture_output=True, text=True)
    remote = subprocess.run(['git', 'rev-parse', '@{u}'], cwd=c.ROOT, check=True, capture_output=True, text=True)
    if head.stdout.strip() != remote.stdout.strip():
        raise subprocess.CalledProcessError(1, 'git push', output='remote branch does not hold HEAD')


def remote_paths():
    """Every path any new remote commit touched (both sides of a rename, each commit on its own)."""
    out = subprocess.run(['git', '-c', 'core.quotepath=false', 'log', '-m', '--no-renames', '--name-only', '-z',
                          '--format=', 'HEAD..@{u}'], cwd=c.ROOT, check=True, capture_output=True).stdout
    return {p for p in out.decode('utf-8').replace('\n', '\0').split('\0') if p}


def replay_on_remote(paths=None):
    """The branch moved during the run. Only when the new remote commits touch nothing in the state
    area (a code or document push) are this run's state commits replayed on top of them, once;
    any remote state change is another writer's state and fails as before. paths is ignored
    (kept for callers of the P version): the rule is the state area, not this run's file list."""
    subprocess.run(['git', 'fetch', '--quiet'], cwd=c.ROOT, check=True)
    touched = sorted(p for p in remote_paths() if state_area(p))
    if touched:
        raise subprocess.CalledProcessError(1, 'git push', output=f'remote changed state {touched[:3]}: not replayed')
    if subprocess.run(['git', 'rebase', '--quiet', '@{u}'], cwd=c.ROOT).returncode != 0:
        subprocess.run(['git', 'rebase', '--abort'], cwd=c.ROOT)
        raise subprocess.CalledProcessError(1, 'git rebase', output='state commits do not replay on the remote')


def persist(message):
    """Commit and push the named state now; False when the remote did not receive it."""
    try:
        main(message)
    except (subprocess.CalledProcessError, OSError, ValueError) as error:
        print(f'[persist] not saved remotely: {type(error).__name__}')
        return False
    return True


if __name__ == '__main__':
    main()
