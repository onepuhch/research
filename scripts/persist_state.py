"""Persist only named research state; never stage credentials or arbitrary files."""
import subprocess
import common as c

STATE_FILES = ['source_state.json', 'seen_sources.json', 'notify_state.json', 'run_status.json',
               'telegram_offset.json', 'command_queue.json', 'pending_tables.json', 'reddit_watch.csv']


def main():
    files = [c.csv_path(table) for table in c.TABLES] + [c.DATA_DIR / name for name in STATE_FILES]
    files += list((c.ROOT / 'data' / 'archive' / 'pre_v2').glob('*'))
    tracked = set(subprocess.run(['git', 'ls-files', '-z'], cwd=c.ROOT, check=True,
                                 capture_output=True, text=True, encoding='utf-8').stdout.split('\0'))
    # Stage deletion of a recovered journal as well as existing state files.
    paths = [p.relative_to(c.ROOT).as_posix() for p in files
             if p.is_file() or p.relative_to(c.ROOT).as_posix() in tracked]
    subprocess.run(['git', 'add', '--', *paths], cwd=c.ROOT, check=True)
    if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=c.ROOT).returncode == 0:
        return
    subprocess.run(['git', 'diff', '--cached', '--check'], cwd=c.ROOT, check=True)
    subprocess.run(['git', 'commit', '-m', f'chore: research state {c.today()}'], cwd=c.ROOT, check=True)
    # On conflict, fail visibly; never force-push a competing writer's state.
    subprocess.run(['git', 'push'], cwd=c.ROOT, check=True)


if __name__ == '__main__':
    main()
