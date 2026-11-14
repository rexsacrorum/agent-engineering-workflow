import importlib.util
import json
import os
from pathlib import Path
import tempfile
import subprocess
import unittest


SPEC = importlib.util.spec_from_file_location('workflow', Path(__file__).resolve().parents[1] / 'scripts/workflow.py')
workflow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow)


class InstallTests(unittest.TestCase):
    def test_install_is_idempotent_and_preserves_unrelated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / 'settings.json').write_text('{}\n')
            self.assertEqual(workflow.install(home), 10)
            self.assertEqual(workflow.install(home), 10)
            self.assertEqual((home / 'settings.json').read_text(), '{}\n')
            root = Path((home / 'skills/engineering-workflow/package-root.txt').read_text().strip())
            self.assertTrue((root / 'docs/agent-workflow/coordination.md').is_file())
            agents = list((home / 'agents').glob('workflow_*.md'))
            self.assertEqual(len(agents), 8)
            for agent in agents:
                fields, _ = workflow.frontmatter(agent)
                self.assertIn(fields['effort'], workflow.EFFORTS)
                self.assertTrue((root / f'docs/agent-workflow/roles/{agent.stem}.md').is_file())

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
            self.assertEqual(workflow.install(link), 10)
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
            self.assertEqual(totals[('advisor', 'model-top')], {
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
            self.assertEqual(sorted(totals), [('advisor', 'model-top'), ('main', 'model-a')])
            self.assertEqual(totals[('advisor', 'model-top')]['input_tokens'], 7)
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


if __name__ == '__main__':
    unittest.main()
