"""Claude Code SessionStart hook: tell a new session that the current branch has a task record.

A task record carries a task from one session to the next, but a new session does not know it
exists. This hook looks for the record named after the current branch and, when it finds one,
prints its path. Claude Code adds what a SessionStart hook prints to the session's context.

The record is `task-records/<name>.md` inside the repository's Git directory, where `<name>` is
the branch name with every `/` replaced by `-`. When no record matches the branch, the hook names
the records changed in the last 14 days, because a task can move to another branch. It prints
nothing when there is no record, outside a Git repository, and on any error. It reads only.

Settings, as environment variables:
  WORKFLOW_TASK_RECORDS  the directory that holds the records; a relative path is taken from the
                         session's directory (default: `task-records` in the Git directory that
                         every worktree of the clone shares)

Python 3.11+, standard library only.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import time


RECENT_DAYS = 14
MAX_NAMED = 5


def git(cwd, *arguments):
    # Git prints paths and branch names in UTF-8, whatever encoding Python would pick for a pipe.
    done = subprocess.run(['git', '-C', str(cwd), *arguments], capture_output=True, timeout=5,
                          encoding='utf-8', errors='surrogateescape')
    return done.stdout.strip() if done.returncode == 0 else ''


def records_directory(cwd):
    configured = os.environ.get('WORKFLOW_TASK_RECORDS', '').strip()
    if configured:
        return (Path(cwd) / configured).resolve()
    common = git(cwd, 'rev-parse', '--git-common-dir')
    return (Path(cwd) / common / 'task-records').resolve() if common else None


def record_name(branch):
    return branch.replace('/', '-') + '.md'


def message(cwd):
    directory = records_directory(cwd)
    if directory is None or not directory.is_dir():
        return ''
    branch = git(cwd, 'branch', '--show-current')
    if branch:
        record = directory / record_name(branch)
        if record.is_file():
            return (f'This branch has a task record: {record.as_posix()}\n'
                    'It holds the request, the acceptance criteria with their status, the decisions, '
                    'the evidence, and what remains. An earlier session of the same task wrote it, '
                    'and the next session reads it before planning. '
                    'Where it differs from the live Git and remote state, Git is right.')
    newest_first = sorted(directory.glob('*.md'), key=lambda path: path.stat().st_mtime, reverse=True)
    limit = time.time() - RECENT_DAYS * 86400
    recent = [path for path in newest_first if path.stat().st_mtime >= limit][:MAX_NAMED]
    if not recent:
        return ''
    where = f'the branch {branch}' if branch else 'this checkout, which is on no branch'
    names = ', '.join(path.name for path in recent)
    return (f'No task record is named after {where}. Records changed in the last {RECENT_DAYS} days '
            f'in {directory.as_posix()}: {names}. A task can move to a new branch; '
            'when this session continues one of these tasks, its record is the one to read.')


def main():
    try:
        # The client sends UTF-8. Read bytes, so the platform's own encoding is not applied.
        event = json.loads(sys.stdin.buffer.read())
        text = message(event.get('cwd') or os.getcwd())
        if text:
            sys.stdout.buffer.write((text + '\n').encode('utf-8', errors='replace'))
    except Exception:  # A hook that fails must not disturb the start of a session.
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
