import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


HOOK = Path(__file__).resolve().parents[1] / 'templates/hooks/task_record.py'
SPEC = importlib.util.spec_from_file_location('task_record', HOOK)
task_record = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(task_record)


def git(repo, *arguments):
    subprocess.run(['git', '-C', str(repo), *arguments], check=True, capture_output=True)


def new_repo(directory, branch='task/sign-in'):
    repo = Path(directory) / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'checkout', '-q', '-b', branch)
    git(repo, '-c', 'user.name=t', '-c', 'user.email=t@example.com', 'commit', '-q', '--allow-empty', '-m', 'start')
    return repo


def write_record(repo, name, age_days=0):
    records = repo / '.git' / 'task-records'
    records.mkdir(exist_ok=True)
    record = records / name
    record.write_text('# Task record\n', encoding='utf-8')
    if age_days:
        then = time.time() - age_days * 86400
        os.utime(record, (then, then))
    return record


class TaskRecordHookTests(unittest.TestCase):
    def test_names_the_record_of_the_current_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = new_repo(directory)
            record = write_record(repo, 'task-sign-in.md')
            text = task_record.message(repo)
            self.assertIn(record.resolve().as_posix(), text)
            self.assertIn('Git is right', text)

    def test_a_worktree_finds_the_record_of_the_clone(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = new_repo(directory, branch='main')
            record = write_record(repo, 'task-payments.md')
            worktree = Path(directory) / 'second'
            git(repo, 'worktree', 'add', '-q', '-b', 'task/payments', str(worktree))
            self.assertIn(record.resolve().as_posix(), task_record.message(worktree))

    def test_a_subdirectory_finds_the_record(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = new_repo(directory)
            record = write_record(repo, 'task-sign-in.md')
            deep = repo / 'src' / 'app'
            deep.mkdir(parents=True)
            self.assertIn(record.resolve().as_posix(), task_record.message(deep))

    def test_no_branch_names_recent_records(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = new_repo(directory)
            write_record(repo, 'task-sign-in.md')
            git(repo, 'checkout', '-q', '--detach')
            text = task_record.message(repo)
            self.assertIn('task-sign-in.md', text)
            self.assertIn('on no branch', text)

    def test_a_path_outside_ascii_is_read_as_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / 'Bogd\u00e1n \u043f\u0440\u043e\u0435\u043a\u0442'
            base.mkdir()
            repo = new_repo(base)
            record = write_record(repo, 'task-sign-in.md')
            event = json.dumps({'hook_event_name': 'SessionStart', 'cwd': str(repo)}, ensure_ascii=False)
            done = subprocess.run([sys.executable, str(HOOK)], input=event.encode('utf-8'), capture_output=True)
            self.assertEqual(done.returncode, 0)
            self.assertIn(record.resolve().as_posix(), done.stdout.decode('utf-8'))

    def test_silent_without_records_and_outside_a_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = new_repo(directory)
            self.assertEqual(task_record.message(repo), '')
            (repo / '.git' / 'task-records').mkdir()
            self.assertEqual(task_record.message(repo), '')
            outside = Path(directory) / 'plain'
            outside.mkdir()
            with patch.dict(os.environ, {'GIT_CEILING_DIRECTORIES': str(Path(directory))}):
                self.assertEqual(task_record.message(outside), '')

    def test_names_recent_records_when_none_matches_the_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = new_repo(directory)
            write_record(repo, 'task-payments.md')
            write_record(repo, 'old-task.md', age_days=task_record.RECENT_DAYS + 1)
            text = task_record.message(repo)
            self.assertIn('task-payments.md', text)
            self.assertNotIn('old-task.md', text)
            self.assertIn('task/sign-in', text)

    def test_old_records_alone_are_not_named(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = new_repo(directory)
            write_record(repo, 'old-task.md', age_days=task_record.RECENT_DAYS + 1)
            self.assertEqual(task_record.message(repo), '')

    def test_a_configured_directory_replaces_the_default(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = new_repo(directory)
            records = repo / 'notes'
            records.mkdir()
            (records / 'task-sign-in.md').write_text('# Task record\n', encoding='utf-8')
            with patch.dict(os.environ, {'WORKFLOW_TASK_RECORDS': 'notes'}):
                self.assertIn('notes/task-sign-in.md', task_record.message(repo))

    def test_runs_as_a_session_start_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = new_repo(directory)
            record = write_record(repo, 'task-sign-in.md')
            event = json.dumps({'hook_event_name': 'SessionStart', 'source': 'startup', 'cwd': str(repo)})
            done = subprocess.run([sys.executable, str(HOOK)], input=event, capture_output=True, text=True,
                                  encoding='utf-8')
            self.assertEqual(done.returncode, 0)
            self.assertIn(record.resolve().as_posix(), done.stdout)
            self.assertEqual(done.stderr, '')

    def test_bad_input_prints_nothing_and_succeeds(self):
        for sent in ('', 'not json', '[]', json.dumps({'cwd': 'Z:/no/such/directory'})):
            with self.subTest(sent=sent):
                done = subprocess.run([sys.executable, str(HOOK)], input=sent, capture_output=True, text=True)
                self.assertEqual(done.returncode, 0)
                self.assertEqual(done.stdout, '')


if __name__ == '__main__':
    unittest.main()
