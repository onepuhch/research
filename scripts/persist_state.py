"""Persist only named research state; never stage credentials or arbitrary files."""
import subprocess
import common as c

STATE_FILES = ['source_state.json', 'seen_sources.json', 'notify_state.json', 'run_status.json', 'daily_runs.json',
               'telegram_offset.json', 'command_queue.json', 'pending_tables.json', 'reddit_watch.csv',
               'model_budget.json', 'candidate_alerts.json']


def main(message=None):
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
    files += [c.DATA_DIR / 'candidates' / 'index.json', c.DATA_DIR / 'candidate_evidence.json',
              c.DATA_DIR / 'translation_cache.json', c.DATA_DIR / 'translation_rejects.json']
    files += [c.ROOT / 'docs' / 'data_history.md', c.ROOT / 'docs' / 'revision_screen.md',
              c.ROOT / 'docs' / 'candidates.md']
    tracked = set(subprocess.run(['git', 'ls-files', '-z'], cwd=c.ROOT, check=True,
                                 capture_output=True, text=True, encoding='utf-8').stdout.split('\0'))
    # Stage deletion of a recovered journal as well as existing state files.
    paths = [p.relative_to(c.ROOT).as_posix() for p in files
             if p.is_file() or p.relative_to(c.ROOT).as_posix() in tracked]
    subprocess.run(['git', 'add', '--', *paths], cwd=c.ROOT, check=True)
    if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=c.ROOT).returncode != 0:
        subprocess.run(['git', 'diff', '--cached', '--check'], cwd=c.ROOT, check=True)
        subprocess.run(['git', 'commit', '-m', message or f'chore: research state {c.today()}'], cwd=c.ROOT, check=True)
    # Push even with nothing new staged: an earlier commit may not have reached the remote.
    # On conflict, fail visibly; never force-push a competing writer's state.
    subprocess.run(['git', 'push'], cwd=c.ROOT, check=True)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=c.ROOT, check=True, capture_output=True, text=True)
    remote = subprocess.run(['git', 'rev-parse', '@{u}'], cwd=c.ROOT, check=True, capture_output=True, text=True)
    if head.stdout.strip() != remote.stdout.strip():
        raise subprocess.CalledProcessError(1, 'git push', output='remote branch does not hold HEAD')


def persist(message):
    """Commit and push the named state now; False when the remote did not receive it."""
    try:
        main(message)
    except (subprocess.CalledProcessError, OSError) as error:
        print(f'[persist] not saved remotely: {type(error).__name__}')
        return False
    return True


if __name__ == '__main__':
    main()
