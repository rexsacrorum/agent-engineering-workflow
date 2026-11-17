import contextlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


HOOK = Path(__file__).resolve().parents[1] / 'templates/hooks/trim_output.py'
SPEC = importlib.util.spec_from_file_location('trim_output', HOOK)
trim_output = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trim_output)


def bash_call(command, **extra):
    return {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {'command': command, **extra}}


def usable_shells():
    """The shells the Bash tool may use, as (shell, python command) pairs: bash, and zsh where it is
    installed, as on macOS. On Windows only Git Bash understands the paths this platform gives."""
    found = []
    for name in ('bash', 'zsh'):
        shell = shutil.which(name)
        if not shell:
            continue
        if os.name == 'nt':
            probe = subprocess.run([shell, '-c', 'echo $MSYSTEM'], capture_output=True, text=True)
            if probe.returncode or not probe.stdout.strip():
                continue
        # macOS and most Linux systems have python3 and no python; Windows has python.
        for python in ('python3', 'python'):
            if subprocess.run([shell, '-c', f'{python} -c "import json"'], capture_output=True).returncode == 0:
                found.append((shell, python))
                break
    return found


class TrimOutputTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        cleared = {name: value for name, value in os.environ.items() if not name.startswith('WORKFLOW_TRIM_')}
        cleared['WORKFLOW_TRIM_DIR'] = self.directory.name
        environment = patch.dict(os.environ, cleared, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def test_a_plain_test_command_is_rewritten_and_other_fields_are_kept(self):
        answer = trim_output.decide(bash_call('  pytest -q tests  ', description='Run tests', timeout=5000))
        updated = answer['hookSpecificOutput']['updatedInput']
        self.assertEqual(answer['hookSpecificOutput']['hookEventName'], 'PreToolUse')
        self.assertNotIn('permissionDecision', answer['hookSpecificOutput'])
        self.assertEqual((updated['description'], updated['timeout']), ('Run tests', 5000))
        self.assertTrue(updated['command'].startswith('echo "[full output: '), updated['command'])
        self.assertIn('; ( pytest -q tests ) > ', updated['command'])
        self.assertIn('tail -n 60 ', updated['command'])
        self.assertTrue(updated['command'].endswith('( exit $rc )'))
        # The rewritten command is not plain, so a second pass leaves it alone.
        self.assertEqual(trim_output.decide(bash_call(updated['command'])), {})

    def test_everything_else_passes_unchanged(self):
        unchanged = [
            bash_call('pytest -q | tail -5'),
            bash_call('pytest -q && echo done'),
            bash_call('pytest -q > out.txt'),
            bash_call('pytest $(git ls-files)'),
            bash_call('pytest -q\nrm -rf build'),
            bash_call('CI=1 pytest -q'),
            bash_call('pytestx -q'),
            bash_call('git status'),
            bash_call('pytest -q', run_in_background=True),
            {'tool_name': 'PowerShell', 'tool_input': {'command': 'pytest -q'}},
            {'tool_name': 'Bash', 'tool_input': {'command': None}},
            {'tool_name': 'Bash'},
            'not an object',
        ]
        for hook_input in unchanged:
            self.assertEqual(trim_output.decide(hook_input), {}, hook_input)

    def test_the_default_list_covers_both_names_of_the_interpreter(self):
        for command in ('python -m pytest -q', 'python3 -m pytest -q', 'python3 -m unittest discover -s tests'):
            self.assertIn('hookSpecificOutput', trim_output.decide(bash_call(command)), command)
        self.assertEqual(trim_output.decide(bash_call('python3 manage.py runserver')), {})

    def test_settings_come_from_the_environment(self):
        with patch.dict(os.environ, {'WORKFLOW_TRIM_COMMANDS': 'just test, tox', 'WORKFLOW_TRIM_LINES': '5'}):
            self.assertEqual(trim_output.decide(bash_call('pytest -q')), {})
            command = trim_output.decide(bash_call('just test'))['hookSpecificOutput']['updatedInput']['command']
            self.assertIn('tail -n 5 ', command)
        with patch.dict(os.environ, {'WORKFLOW_TRIM_LINES': 'many'}):
            command = trim_output.decide(bash_call('make'))['hookSpecificOutput']['updatedInput']['command']
            self.assertIn('tail -n 60 ', command)

    def test_the_output_file_goes_to_the_session_scratchpad_by_default(self):
        scratchpad = Path(self.directory.name) / 'scratch pad'
        with patch.dict(os.environ):
            del os.environ['WORKFLOW_TRIM_DIR']
            answer = trim_output.decide({**bash_call('go test ./...'), 'scratchpad_dir': str(scratchpad)})
        self.assertIn(scratchpad.as_posix(), answer['hookSpecificOutput']['updatedInput']['command'])
        self.assertTrue(scratchpad.is_dir())

    def test_without_a_usable_scratchpad_the_output_file_goes_to_the_temp_directory(self):
        temp = Path(self.directory.name) / 'temp'
        with patch.dict(os.environ), patch.object(trim_output.tempfile, 'gettempdir', return_value=str(temp)):
            del os.environ['WORKFLOW_TRIM_DIR']
            mine = trim_output.fallback_directory()
            self.assertEqual(mine.parent, temp)
            self.assertRegex(mine.name, r'^claude-output-.+')
            for scratchpad in (5, None, ''):
                answer = trim_output.decide({**bash_call('go test ./...'), 'scratchpad_dir': scratchpad})
                self.assertIn(mine.as_posix() + '/output-',
                              answer['hookSpecificOutput']['updatedInput']['command'], scratchpad)
            if os.name != 'nt':  # nobody else on a shared machine may read or replace the logs
                self.assertEqual(stat.S_IMODE(mine.stat().st_mode), 0o700)

    def test_a_user_name_with_shell_characters_still_gets_a_usable_directory(self):
        # Where there is no numeric user id (Windows), the directory carries the user's name.
        user_id = getattr(os, 'getuid', None)
        if user_id:
            del os.getuid
            self.addCleanup(setattr, os, 'getuid', user_id)
        temp = Path(self.directory.name) / 'temp'
        with patch.dict(os.environ), patch.object(trim_output.tempfile, 'gettempdir', return_value=str(temp)), \
                patch.object(trim_output.getpass, 'getuser', return_value='R&D $(x) "й"'):
            del os.environ['WORKFLOW_TRIM_DIR']
            self.assertEqual(trim_output.fallback_directory().name, 'claude-output-R_D___x___й_')
            command = trim_output.decide(bash_call('make'))['hookSpecificOutput']['updatedInput']['command']
        self.assertIn('/claude-output-R_D___x___й_/output-', command)

    def test_the_output_file_exists_before_the_command_runs_and_each_call_gets_its_own(self):
        commands = [trim_output.decide(bash_call('make'))['hookSpecificOutput']['updatedInput']['command']
                    for _ in range(3)]
        files = {command.split('[full output: ', 1)[1].split(']', 1)[0] for command in commands}
        self.assertEqual(len(files), 3)
        for name in files:
            self.assertEqual(Path(name).read_bytes(), b'')

    def test_a_directory_that_cannot_take_the_file_leaves_the_command_unchanged(self):
        blocker = Path(self.directory.name) / 'a-file'
        blocker.write_text('not a directory')
        with patch.dict(os.environ, {'WORKFLOW_TRIM_DIR': str(blocker / 'logs')}):
            self.assertEqual(trim_output.decide(bash_call('make')), {})
        if os.name == 'nt' or os.geteuid() == 0:
            return  # permission bits and links need a non-root POSIX user
        locked = Path(self.directory.name) / 'locked'
        locked.mkdir(mode=0o555)
        with patch.dict(os.environ, {'WORKFLOW_TRIM_DIR': str(locked)}):
            self.assertEqual(trim_output.decide(bash_call('make')), {})
        # Another user created the shared fallback name first, as a link to a place of their choice.
        temp = Path(self.directory.name) / 'shared-temp'
        elsewhere = Path(self.directory.name) / 'elsewhere'
        temp.mkdir()
        elsewhere.mkdir()
        with patch.dict(os.environ), patch.object(trim_output.tempfile, 'gettempdir', return_value=str(temp)):
            del os.environ['WORKFLOW_TRIM_DIR']
            trim_output.fallback_directory().symlink_to(elsewhere, target_is_directory=True)
            self.assertEqual(trim_output.decide(bash_call('make')), {})
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_a_relative_output_directory_is_taken_from_the_commands_directory(self):
        work = Path(self.directory.name) / 'project'
        work.mkdir()
        with patch.dict(os.environ, {'WORKFLOW_TRIM_DIR': 'logs'}):
            answer = trim_output.decide({**bash_call('make'), 'cwd': str(work)})
        self.assertIn((work / 'logs').as_posix() + '/output-', answer['hookSpecificOutput']['updatedInput']['command'])
        self.assertTrue((work / 'logs').is_dir())

    def test_without_a_usable_cwd_a_relative_directory_is_taken_from_the_hooks_own_directory(self):
        here = Path(self.directory.name).resolve() / 'hook-process'
        here.mkdir()
        with patch.dict(os.environ, {'WORKFLOW_TRIM_DIR': 'logs'}), contextlib.chdir(here):
            for working in (None, 5, ''):
                answer = trim_output.decide({**bash_call('make'), 'cwd': working})
                self.assertIn((here / 'logs').as_posix() + '/output-',
                              answer['hookSpecificOutput']['updatedInput']['command'], working)

    def test_a_command_with_non_ascii_text_reaches_the_shell_unchanged(self):
        # The client sends UTF-8 whatever encoding Python would pick for its streams. Forcing
        # another one here makes the test fail on every platform if the hook reads text again.
        sent = json.dumps(bash_call('pytest tests/test_café.py -k "naïve"'), ensure_ascii=False).encode('utf-8')
        done = subprocess.run([sys.executable, str(HOOK)], input=sent, capture_output=True,
                              env={**os.environ, 'PYTHONIOENCODING': 'latin-1'})
        self.assertEqual(done.returncode, 0, done.stderr)
        command = json.loads(done.stdout)['hookSpecificOutput']['updatedInput']['command']
        self.assertIn('; ( pytest tests/test_café.py -k "naïve" ) > ', command)

    def test_the_script_answers_on_stdout_and_never_fails_on_bad_input(self):
        deep = '[' * 100000 + ']' * 100000
        for text, rewritten in ((json.dumps(bash_call('cargo test')), True), ('not json', False), ('', False),
                                (deep, False)):
            done = subprocess.run([sys.executable, str(HOOK)], input=text, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual('hookSpecificOutput' in json.loads(done.stdout), rewritten, text)

    def test_the_rewritten_command_keeps_the_exit_status_and_the_full_output(self):
        shells = usable_shells()
        if not shells:
            self.skipTest('needs bash or zsh with python')
        work = Path(self.directory.name)
        # The last line has no newline, and the output directory needs quoting.
        (work / 'noisy.py').write_text(
            'import sys\nfor n in range(200):\n    print("line", n)\n'
            'print("oops", file=sys.stderr)\nsys.stdout.write("end")\nsys.exit(3)\n')
        for shell, python in shells:
            with self.subTest(shell=shell):
                settings = {'WORKFLOW_TRIM_COMMANDS': python, 'WORKFLOW_TRIM_LINES': '10',
                            'WORKFLOW_TRIM_DIR': "out put's"}
                with patch.dict(os.environ, settings):
                    answer = trim_output.decide({**bash_call(f'{python} noisy.py'), 'cwd': str(work)})
                command = answer['hookSpecificOutput']['updatedInput']['command']
                done = subprocess.run([shell, '-c', command], cwd=work, capture_output=True, text=True)
                self.assertEqual(done.returncode, 3, done.stderr)
                shown = done.stdout.splitlines()
                self.assertTrue(shown[0].startswith('[full output: '), shown[0])
                self.assertEqual(shown[-2:], ['end', '[exit 3; last 10 lines shown]'])
                self.assertEqual(len(shown), 12)
                self.assertIn('line 199', shown)
                self.assertNotIn('line 5', shown)
                saved = Path(shown[0].split('full output: ', 1)[1].rstrip(']'))
                self.assertEqual(saved.parent, work / "out put's")
                self.assertEqual(saved.read_text().count('line '), 200)
                self.assertIn('oops', saved.read_text())
                saved.unlink()

    def test_a_passing_command_and_one_whose_glob_matches_nothing(self):
        shells = usable_shells()
        if not shells:
            self.skipTest('needs bash or zsh with python')
        work = Path(self.directory.name)
        (work / 'quiet.py').write_text('print("fine")\n')
        for shell, python in shells:
            with self.subTest(shell=shell), patch.dict(os.environ, {'WORKFLOW_TRIM_COMMANDS': python}):
                def run(command):
                    answer = trim_output.decide({**bash_call(command), 'cwd': str(work)})
                    rewritten = answer['hookSpecificOutput']['updatedInput']['command']
                    return subprocess.run([shell, '-c', rewritten], cwd=work, capture_output=True, text=True)

                passed = run(f'{python} quiet.py')
                self.assertEqual(passed.returncode, 0, passed.stderr)
                self.assertEqual(passed.stdout.splitlines()[1:], ['fine', '', '[exit 0; last 60 lines shown]'])
                # bash passes an unmatched pattern on and the command fails; zsh refuses it. Either
                # way the agent gets the reason, the closing line and a failing status.
                unmatched = run(f'{python} nothing-here-*.py')
                self.assertNotEqual(unmatched.returncode, 0)
                shown = unmatched.stdout.splitlines()
                self.assertIn('nothing-here', '\n'.join(shown[1:-1]), unmatched.stderr)
                self.assertRegex(shown[-1], r'^\[exit [1-9]\d*; last 60 lines shown\]$')

if __name__ == '__main__':
    unittest.main()
