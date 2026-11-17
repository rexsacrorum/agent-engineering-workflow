import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import subprocess
import sys
import unittest


SPEC = importlib.util.spec_from_file_location('workflow', Path(__file__).resolve().parents[1] / 'scripts/workflow.py')
workflow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow)


class InstallTests(unittest.TestCase):
    def test_install_is_idempotent_and_preserves_unrelated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / 'settings.json').write_text('{}\n')
            self.assertEqual(workflow.install(home), 9)
            self.assertEqual(workflow.install(home), 9)
            self.assertEqual((home / 'settings.json').read_text(), '{}\n')
            root = Path((home / 'skills/engineering-workflow/package-root.txt').read_text().strip())
            self.assertTrue((root / 'docs/agent-workflow/coordination.md').is_file())
            agents = list((home / 'agents').glob('workflow_*.md'))
            self.assertEqual(len(agents), 7)
            for agent in agents:
                fields, _ = workflow.frontmatter(agent)
                self.assertIn(fields['effort'], workflow.EFFORTS)
                self.assertTrue((root / f'docs/agent-workflow/roles/{agent.stem}.md').is_file())

    def test_read_only_roles_are_denied_the_editing_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory) / 'home'
            workflow.install(home)
            for role in workflow.ROLES:
                fields, _ = workflow.frontmatter(home / f'agents/workflow_{role}.md')
                denied = set(fields.get('disallowedTools', '').replace(',', ' ').split())
                self.assertEqual(denied, workflow.EDITING_TOOLS if role in workflow.READ_ONLY else set(), role)
            # A package whose reviewer may edit does not validate, so it cannot be installed.
            package = Path(directory) / 'package'
            shutil.copytree(workflow.PACKAGE, package, ignore=shutil.ignore_patterns('.git', '__pycache__', 'tmp'))
            wiring = package / '.claude/agents/workflow_reviewer.md'
            wiring.write_text(wiring.read_text().replace('disallowedTools: Write, Edit, NotebookEdit\n',
                                                          'disallowedTools: Write\n'))
            with self.assertRaisesRegex(ValueError, 'read-only role'):
                workflow.validate(package)
            # Brackets and quotes on one line are read; the order does not matter.
            wiring.write_text(wiring.read_text().replace('disallowedTools: Write\n',
                                                          'disallowedTools: ["NotebookEdit", Edit, Write]\n'))
            workflow.validate(package)

    def test_replace_backs_up_differing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            role = home / 'agents/workflow_verifier.md'
            role.parent.mkdir()
            role.write_text('# older installation\n')
            workflow.install(home, replace=True)
            self.assertIn(b'roles/workflow_verifier.md', role.read_bytes())
            backups = list((home / 'workflow-backups').glob('*/agents/workflow_verifier.md'))
            self.assertEqual([path.read_text() for path in backups], ['# older installation\n'])

    def test_conflict_leaves_all_destinations_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            role = home / 'agents/workflow_verifier.md'
            role.parent.mkdir()
            role.write_text('# independently maintained\n')
            with self.assertRaises(ValueError):
                workflow.install(home)
            self.assertEqual(role.read_text(), '# independently maintained\n')
            self.assertFalse((home / 'skills').exists())
            self.assertEqual(list(role.parent.iterdir()), [role])

    def test_linked_destination_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / 'target'
            target.mkdir()
            home = base / 'home'
            home.mkdir()
            try:
                (home / 'agents').symlink_to(target, target_is_directory=True)
            except OSError:
                self.skipTest('Creating directory symlinks is unavailable')
            with self.assertRaises(ValueError):
                workflow.install(home)
            self.assertEqual(list(target.iterdir()), [])
            self.assertFalse((home / 'skills').exists())

    def test_home_reached_through_a_link_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            real = base / 'real-home'
            real.mkdir()
            link = base / 'linked-home'
            try:
                link.symlink_to(real, target_is_directory=True)
            except OSError:
                self.skipTest('Creating directory symlinks is unavailable')
            self.assertEqual(workflow.install(link), 9)
            self.assertTrue((real / 'skills/engineering-workflow/SKILL.md').is_file())

    @unittest.skipUnless(os.name == 'nt', 'Windows junction test')
    def test_junction_destination_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / 'other-package'
            target.mkdir()
            home = base / 'client-home'
            home.mkdir()
            link = home / 'agents'
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)],
                           check=True, capture_output=True)
            try:
                with self.assertRaises(ValueError):
                    workflow.install(home)
                self.assertEqual(list(target.iterdir()), [])
                self.assertFalse((home / 'skills').exists())
            finally:
                # rmdir removes the junction itself, not the target directory.
                os.rmdir(link)
            # A linked backup directory is refused before anything is replaced.
            role = home / 'agents/workflow_verifier.md'
            role.parent.mkdir()
            role.write_text('# older installation\n')
            backups = home / 'workflow-backups'
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(backups), str(target)],
                           check=True, capture_output=True)
            try:
                with self.assertRaises(ValueError):
                    workflow.install(home, replace=True)
                self.assertEqual(list(target.iterdir()), [])
                self.assertEqual(role.read_text(), '# older installation\n')
            finally:
                os.rmdir(backups)


def assistant(message_id, model='model-a', **usage):
    return {'type': 'assistant', 'timestamp': '2026-01-01T00:00:00Z',
            'message': {'id': message_id, 'model': model, 'usage': usage}}


def write_lines(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(record) + '\n' for record in records), encoding='utf-8')


class UsageTests(unittest.TestCase):
    def test_counts_each_message_once_and_groups_by_role_and_model(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory) / 'session.jsonl'
            advisor_part = {'type': 'advisor_message', 'model': 'model-top', 'input_tokens': 50, 'output_tokens': 4}
            own_part = {'type': 'message', 'input_tokens': 3, 'cache_creation_input_tokens': 20, 'output_tokens': 5}
            write_lines(session, [
                {'type': 'user', 'timestamp': '2025-12-31T23:00:00Z', 'message': {'content': 'hello'}},
                # One message, written once per content block: the last line holds the final counts.
                assistant('m1', cache_read_input_tokens=100, output_tokens=1),
                assistant('m1', cache_read_input_tokens=100, output_tokens=7),
                # The message's own part repeats its totals; the advisor part is extra.
                assistant('m2', input_tokens=3, cache_creation_input_tokens=20, output_tokens=5,
                          iterations=[own_part, advisor_part]),
                assistant('m3', model='<synthetic>', input_tokens=0, output_tokens=0, iterations=None),
            ])
            agents = session.with_suffix('') / 'subagents'
            for name, model in (('agent-1', 'model-b'), ('agent-2', 'model-b'), ('agent-3', 'model-c')):
                write_lines(agents / f'{name}.jsonl', [assistant(name, model=model, cache_read_input_tokens=10)])
                (agents / f'{name}.meta.json').write_text('{"agentType": "workflow_reviewer"}')
            write_lines(agents / 'agent-4.jsonl', [assistant('x', output_tokens=2)])
            totals, span = workflow.session_usage(session)
            self.assertEqual(totals[('main', 'model-a')], {
                'agents': 1, 'requests': 2, 'input_tokens': 3,
                'cache_read_input_tokens': 100, 'cache_creation_input_tokens': 20, 'output_tokens': 12})
            self.assertEqual(totals[('advisor, called by main', 'model-top')], {
                'agents': 1, 'requests': 1, 'input_tokens': 50,
                'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0, 'output_tokens': 4})
            # A tier override shows as its own row: same role, another model.
            self.assertEqual((totals[('workflow_reviewer', 'model-b')]['agents'],
                              totals[('workflow_reviewer', 'model-b')]['cache_read_input_tokens']), (2, 20))
            self.assertEqual(totals[('workflow_reviewer', 'model-c')]['agents'], 1)
            self.assertEqual(totals[('unknown', 'model-a')]['output_tokens'], 2)
            self.assertEqual(len(totals), 5)
            self.assertEqual(span, ('2025-12-31T23:00:00Z', '2026-01-01T00:00:00Z'))
            table = workflow.format_usage(totals, span).splitlines()
            self.assertEqual(table[2], '| main | model-a | 1 | 2 | 3 | 100 | 20 | 12 |')

    def test_unknown_or_inconsistent_usage_parts_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory) / 'session.jsonl'
            for parts in ([{'type': 'new_kind', 'output_tokens': 9}], [{'type': 'message', 'output_tokens': 4}]):
                write_lines(session, [assistant('m1', output_tokens=5, iterations=parts)])
                with self.assertRaises(ValueError, msg=parts):
                    workflow.session_usage(session)

    def test_advisor_only_transcripts(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory) / 'session.jsonl'
            advisor_only = assistant('a1', input_tokens=0, output_tokens=0, iterations=[
                {'type': 'advisor_message', 'model': 'model-top', 'input_tokens': 7, 'output_tokens': 1}])
            write_lines(session, [assistant('m1', output_tokens=5)])
            write_lines(session.with_suffix('') / 'subagents' / 'agent-1.jsonl', [advisor_only])
            totals, _ = workflow.session_usage(session)
            # A subagent that only called the advisor has no row of its own.
            self.assertEqual(sorted(totals), [('advisor, called by unknown', 'model-top'), ('main', 'model-a')])
            self.assertEqual(totals[('advisor, called by unknown', 'model-top')]['input_tokens'], 7)
            # The main transcript must still hold requests of its own.
            write_lines(session, [advisor_only])
            with self.assertRaises(ValueError):
                workflow.session_usage(session)

    def test_unrecognised_transcripts_fail_instead_of_reporting_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            cases = {
                'empty.jsonl': [{'type': 'user', 'message': {'content': 'hello'}}],
                'renamed.jsonl': [{'type': 'assistant', 'message': {'id': 'm1', 'usage': {'tokens_in': 5}}}],
                'no-id.jsonl': [{'type': 'assistant', 'message': {'usage': {'output_tokens': 5}}}],
            }
            for name, records in cases.items():
                write_lines(base / name, records)
                with self.assertRaises(ValueError, msg=name):
                    workflow.session_usage(base / name)
            (base / 'text.jsonl').write_text('not a transcript\n')
            for name in ('text.jsonl', 'missing.jsonl'):
                with self.assertRaises(ValueError, msg=name):
                    workflow.session_usage(base / name)

    def test_advisor_calls_are_split_by_calling_role(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory) / 'session.jsonl'

            def calling(message_id, tokens):
                own = {'type': 'message', 'output_tokens': 5}
                advisor_part = {'type': 'advisor_message', 'model': 'model-top', 'input_tokens': tokens}
                return assistant(message_id, output_tokens=5, iterations=[own, advisor_part])

            write_lines(session, [calling('m1', 300)])
            agents = session.with_suffix('') / 'subagents'
            for name, role, tokens in (('agent-1', 'workflow_implementer', 100),
                                       ('agent-2', 'workflow_implementer', 50), ('agent-3', 'workflow_reviewer', 7)):
                write_lines(agents / f'{name}.jsonl', [calling(name, tokens)])
                (agents / f'{name}.meta.json').write_text(json.dumps({'agentType': role}))
            totals, span = workflow.session_usage(session)

            def row(caller):
                found = totals[(f'advisor, called by {caller}', 'model-top')]
                return found['agents'], found['requests'], found['input_tokens']

            self.assertEqual(row('main'), (1, 1, 300))
            self.assertEqual(row('workflow_implementer'), (2, 2, 150))
            self.assertEqual(row('workflow_reviewer'), (1, 1, 7))
            self.assertIn('| advisor, called by workflow_implementer | model-top | 2 | 2 | 150 |',
                          workflow.format_usage(totals, span))


def said(role, *blocks, kind=None, timestamp='2026-01-01T00:00:00Z'):
    record = {'type': kind or role, 'message': {'role': role, 'content': list(blocks)}}
    if timestamp:
        record['timestamp'] = timestamp
    return record


def call(call_id, name, **arguments):
    return {'type': 'tool_use', 'id': call_id, 'name': name, 'input': arguments}


def result(call_id, content):
    return {'type': 'tool_result', 'tool_use_id': call_id, 'content': content}


class ActivityTests(unittest.TestCase):
    def test_counts_edits_by_role_and_what_main_history_is_made_of(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory) / 'session.jsonl'
            edit = call('e1', 'Edit', file_path='a.py', new_string='x')
            shell = call('b1', 'Bash', command='ls')
            delegate = call('s1', 'Agent', prompt='p')
            write_lines(session, [
                {'type': 'user', 'timestamp': '2026-01-01T00:00:00Z', 'message': {'role': 'user', 'content': 'go'}},
                said('assistant', {'type': 'text', 'text': 'plan'}, {'type': 'thinking', 'thinking': 'long'}),
                said('assistant', edit),
                # The client keeps a copy of the request in a record of another type, without a
                # timestamp. It repeats the call and must not be counted again.
                said('assistant', edit, kind='api-request-blob', timestamp=None),
                # Such a copy is skipped for its type, not only because its ids repeat: neither
                # this text nor this call exists anywhere else.
                said('assistant', {'type': 'text', 'text': 'copied text'},
                     call('e9', 'Edit', file_path='z.py', new_string='y'), kind='api-request-blob', timestamp=None),
                said('user', result('e9', 'copied result'), kind='api-request-blob', timestamp=None),
                # The same call written on a second line of the same kind is still one call.
                said('assistant', edit),
                said('user', result('e1', 'ok')),
                said('user', result('e1', 'ok')),
                said('assistant', shell),
                said('user', result('b1', [{'type': 'text', 'text': 'abc'}, {'type': 'image', 'source': {}}])),
                said('assistant', delegate),
                said('user', result('s1', 'report')),
            ])
            agents = session.with_suffix('') / 'subagents'
            first, second = call('w1', 'Write', file_path='b.py', content='1'), call('w2', 'Write', file_path='c.py', content='2')
            write_lines(agents / 'agent-1.jsonl', [
                said('assistant', first), said('assistant', second),
                said('assistant', first, kind='api-request-blob', timestamp=None),
            ])
            (agents / 'agent-1.meta.json').write_text('{"agentType": "workflow_implementer"}')
            write_lines(agents / 'agent-2.jsonl', [said('assistant', call('r1', 'Read', file_path='b.py'))])
            (agents / 'agent-2.meta.json').write_text('{"agentType": "workflow_reviewer"}')

            edits, history = workflow.session_activity(session)
            self.assertEqual(edits, {'main': 1, 'workflow_implementer': 2, 'workflow_reviewer': 0})
            called = sum(len(json.dumps(block['input'])) for block in (edit, shell, delegate))
            self.assertEqual(history, {'tool calls': called, 'tool output': 5,
                                       'messages, client notes and subagent reports': 8, "the agent's own text": 4})
            lines = workflow.format_activity(edits, history).splitlines()
            self.assertEqual(lines[0], 'File-editing calls: main 1, workflow_implementer 2.')
            self.assertTrue(lines[1].startswith("Main's history by characters: tool calls "), lines[1])

    def test_a_session_without_edits_or_text_reports_none(self):
        self.assertEqual(workflow.format_activity({'main': 0}, dict.fromkeys(workflow.HISTORY_PARTS, 0)),
                         'File-editing calls: none.')


class SessionsTests(unittest.TestCase):
    def test_lists_recent_sessions_and_counts_what_it_leaves_out(self):
        def turn(message_id, stamp, *blocks, **usage):
            return {'type': 'assistant', 'timestamp': stamp, 'cwd': 'C:\\code\\shop\\.claude\\worktrees\\fix',
                    'message': {'id': message_id, 'model': 'model-a', 'role': 'assistant',
                                'content': list(blocks), 'usage': usage}}

        with tempfile.TemporaryDirectory() as directory:
            projects = Path(directory) / 'projects'
            session = projects / 'C--code-shop' / 'abcdef0123456789.jsonl'
            advisor_part = {'type': 'advisor_message', 'model': 'model-top', 'input_tokens': 9}
            write_lines(session, [
                turn('m1', '2026-01-02T10:00:00Z', call('e1', 'Edit', file_path='a.py', new_string='x'),
                     cache_read_input_tokens=2_000_000, output_tokens=500_000),
                said('user', result('e1', 'ok' * 10), timestamp='2026-01-02T10:01:00Z'),
                turn('m2', '2026-01-02T12:30:00Z', {'type': 'text', 'text': 'done'}, output_tokens=5,
                     iterations=[{'type': 'message', 'output_tokens': 5}, advisor_part]),
            ])
            agents = session.with_suffix('') / 'subagents'
            write_lines(agents / 'agent-1.jsonl', [turn('r1', '2026-01-02T11:00:00Z', output_tokens=250_000)])
            (agents / 'agent-1.meta.json').write_text('{"agentType": "workflow_reviewer"}')
            write_lines(projects / 'C--code-shop' / 'old.jsonl',
                        [turn('o1', '2025-12-01T00:00:00Z', output_tokens=1), turn('o2', '2025-12-01T01:00:00Z', output_tokens=1)])
            write_lines(projects / 'C--code-shop' / 'tiny.jsonl', [turn('t1', '2026-01-03T00:00:00Z', output_tokens=1)])
            (projects / 'C--code-shop' / 'broken.jsonl').write_text('not a transcript\n')

            table = workflow.sessions_table(directory, since=workflow.date(2026, 1, 1), least=2).splitlines()
            self.assertEqual(len(table), 4, table)
            self.assertEqual(table[2].split(' | ')[:6],
                             ['| 2026-01-02', 'shop', 'abcdef01', '2.5', '2', '2.00'])
            self.assertIn('| main 0.50, workflow_reviewer 0.25 | workflow_reviewer 1 | main 1 | main 1 | ', table[2])
            self.assertEqual(table[3], '1 sessions listed; 1 with fewer than 2 main requests left out; '
                                       '1 transcripts could not be read.')
            # Another project name, or a later date, lists nothing.
            self.assertIn('0 sessions listed', workflow.sessions_table(directory, project='blog', least=2))
            self.assertIn('0 sessions listed',
                          workflow.sessions_table(directory, since=workflow.date(2026, 2, 1), least=1))

    def test_one_bad_transcript_does_not_stop_the_table(self):
        def request(message_id, stamp, cwd=None):
            record = {'type': 'assistant', 'message': {'id': message_id, 'model': 'model-a',
                                                       'usage': {'output_tokens': 1}}}
            if stamp:
                record['timestamp'] = stamp
            if cwd:
                record['cwd'] = cwd
            return record

        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / 'projects' / 'p'
            # Named so that file order and time order differ.
            write_lines(folder / 'z.jsonl', [request('z1', '2026-01-03T23:00:00Z')])
            write_lines(folder / 'a.jsonl', [request('a1', '2026-01-05T08:00:00Z', cwd='/home/u/blog')])
            write_lines(folder / 'stale.jsonl', [request('s1', '2026-01-04T00:00:00Z', cwd='/')])
            os.utime(folder / 'stale.jsonl', (1_700_000_000, 1_700_000_000))  # written in 2023
            write_lines(folder / 'opened-and-left.jsonl', [{'type': 'user', 'message': {'content': 'hi'}}])
            write_lines(folder / 'no-stamps.jsonl', [request('n1', None)])
            write_lines(folder / 'bad-meta.jsonl', [request('b1', '2026-01-04T00:00:00Z')])
            write_lines(folder / 'bad-meta' / 'subagents' / 'agent-1.jsonl', [request('b2', '2026-01-04T00:00:00Z')])
            (folder / 'bad-meta' / 'subagents' / 'agent-1.meta.json').write_text('[]')

            table = workflow.sessions_table(directory, since=workflow.date(2026, 1, 1), least=1).splitlines()
            self.assertEqual([line.split(' | ')[1] for line in table[2:-1]], ['p', 'blog'])
            self.assertEqual(table[-1], '2 sessions listed; 0 with fewer than 1 main requests left out; '
                                        '2 transcripts could not be read.')
            # Without a date the file's age does not matter; its root directory gives no project name.
            everything = workflow.sessions_table(directory, least=1).splitlines()
            self.assertEqual([line.split(' | ')[1] for line in everything[2:-1]], ['p', 'p', 'blog'])

            script = Path(__file__).resolve().parents[1] / 'scripts/workflow.py'
            done = subprocess.run([sys.executable, str(script), 'sessions', '--home', directory, '--least', '1',
                                   '--since', '2026-01-01', '--project', 'BLOG'], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn('1 sessions listed', done.stdout)

    def test_a_worktree_belongs_to_its_project_and_other_claude_folders_do_not(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Path(directory) / 'folder' / 's.jsonl'
            for cwd, name in (('/work/shop/.claude/worktrees/fix', 'shop'), ('C:\\Users\\u\\.claude\\skills', 'skills'),
                              ('/work/shop', 'shop')):
                write_lines(session, [{'type': 'user', 'cwd': cwd, 'message': {'content': 'hi'}}])
                self.assertEqual(workflow.project_name(session), name, cwd)


if __name__ == '__main__':
    unittest.main()
