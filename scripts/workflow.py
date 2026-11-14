"""Validate or install this workflow package, or report a session's token usage.

Python 3.11+, standard library only.
"""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import stat


PACKAGE = Path(__file__).resolve().parents[1]
ROLES = {'architecture', 'implementer', 'reviewer', 'verifier', 'qa_architect', 'docs', 'delivery', 'advisor'}
MODELS = {'opus', 'sonnet', 'haiku', 'fable', 'inherit'}
EFFORTS = {'low', 'medium', 'high', 'xhigh', 'max'}
POINTER = re.compile(r"docs/agent-workflow/roles/(\w+)\.md")


def frontmatter(path):
    text = path.read_text(encoding='utf-8')
    sections = text.split('---', 2)
    if len(sections) != 3 or sections[0].strip():
        raise ValueError(f'Missing frontmatter: {path}')
    fields = {}
    for line in sections[1].strip().splitlines():
        key, _, value = line.partition(':')
        fields[key.strip()] = value.strip()
    return fields, sections[2]


def validate(package=PACKAGE):
    package = Path(package).resolve()
    skill = package / 'skills' / 'engineering-workflow' / 'SKILL.md'
    fields, _ = frontmatter(skill)
    if fields.get('name') != 'engineering-workflow' or not fields.get('description'):
        raise ValueError(f'Invalid skill metadata: {skill}')
    agents = set()
    for path in (package / '.claude' / 'agents').glob('*.md'):
        fields, body = frontmatter(path)
        if fields.get('name') != path.stem or not fields.get('description'):
            raise ValueError(f'Invalid agent metadata: {path}')
        model = fields.get('model', '')
        if model not in MODELS and not model.startswith('claude-'):
            raise ValueError(f'Unknown model in {path}')
        if fields.get('effort') not in EFFORTS:
            raise ValueError(f'Missing or unknown effort in {path}')
        if POINTER.findall(body) != [path.stem]:
            raise ValueError(f'{path} must point at docs/agent-workflow/roles/{path.stem}.md')
        if not (package / 'docs' / 'agent-workflow' / 'roles' / f'{path.stem}.md').is_file():
            raise ValueError(f'Missing role file for {path}')
        agents.add(path.stem)
    if agents != {f'workflow_{role}' for role in ROLES}:
        raise ValueError('Unexpected or missing workflow agents')
    for path in package.rglob('*.md'):
        if {'.git', 'tmp', 'task-runs'} & set(path.relative_to(package).parts):
            continue
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            if '://' in link or link.startswith('#'):
                continue
            target = link.split('#', 1)[0]
            if target and not (path.parent / target).exists():
                raise ValueError(f'Broken local link in {path}: {link}')
    return len(agents)


def planned_writes(destination, package):
    skill = destination / 'skills' / 'engineering-workflow'
    writes = {
        skill / 'SKILL.md': (package / 'skills' / 'engineering-workflow' / 'SKILL.md').read_bytes(),
        skill / 'package-root.txt': (package.as_posix() + '\n').encode(),
    }
    for path in (package / '.claude' / 'agents').glob('workflow_*.md'):
        writes[destination / 'agents' / path.name] = path.read_bytes()
    return writes


def is_link(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    reparse = getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)
    return bool(stat.S_ISLNK(info.st_mode) or reparse)


def install(home, package=PACKAGE, replace=False):
    package = Path(package).resolve()
    validate(package)
    # The home itself may be reached through links (a dotfiles checkout, /var on macOS):
    # that is the user's choice of home. Links inside it are refused.
    try:
        destination = Path(home).expanduser().resolve()
    except (RuntimeError, OSError) as error:
        raise ValueError(f'Cannot resolve the client home {home}: {error}') from None
    writes = planned_writes(destination, package)
    changed = []
    if is_link(destination / 'workflow-backups'):
        raise ValueError(f"Refusing linked backup directory: {destination / 'workflow-backups'}")
    # Preflight every output before modifying anything. Never follow an installed
    # link into another package.
    for path, content in writes.items():
        for parent in (path, *path.parents):
            if parent == destination:
                break
            if is_link(parent):
                raise ValueError(f'Refusing linked installation path: {parent}')
        if path.exists():
            if not path.is_file():
                raise ValueError(f'Refusing to replace non-file: {path}')
            if path.read_bytes() != content:
                if not replace:
                    raise ValueError(f'Refusing to replace existing file without --replace: {path}')
                changed.append(path)
    if changed:
        backup = destination / 'workflow-backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        for path in changed:
            target = backup / path.relative_to(destination)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    for path, content in writes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path in changed:
            path.write_bytes(content)
        elif not path.exists():
            with path.open('xb') as stream:
                stream.write(content)
    return len(writes)


def default_home():
    return Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude')


TOKEN_FIELDS = ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'output_tokens')
# Parts of one API message. 'message' parts add up to the message's own usage;
# an advisor call is billed separately and is not included in it.
ITERATION_ROLES = {'message': None, 'advisor_message': 'advisor'}


def token_counts(usage, where):
    counts = [usage.get(field) or 0 for field in TOKEN_FIELDS]
    if not all(isinstance(value, int) for value in counts):
        raise ValueError(f'{where} has a non-integer token count')
    return counts


def transcript_usage(path):
    """Sum one Claude Code transcript into {(role or None, model): [requests, *tokens]}.

    The format is not a public interface, so anything unexpected raises instead
    of producing a partial count."""
    messages = {}
    stamps = []
    with open(path, encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            where = f'{path}:{number}'
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f'{where} is not JSON: {error}') from None
            if not isinstance(record, dict):
                raise ValueError(f'{where} is not a JSON object')
            if isinstance(record.get('timestamp'), str):
                stamps.append(record['timestamp'])
            message = record.get('message')
            if record.get('type') != 'assistant' or not isinstance(message, dict) or 'usage' not in message:
                continue
            usage = message['usage']
            if not isinstance(message.get('id'), str) or not isinstance(usage, dict):
                raise ValueError(f'{where} has an assistant message without id or usage fields')
            if not any(field in usage for field in TOKEN_FIELDS):
                raise ValueError(f'{where} has usage without known token fields')
            # A message is written once per content block; the last line carries its final counts.
            messages[message['id']] = (message.get('model') or 'unknown', usage, where)
    rows = {}
    for model, usage, where in messages.values():
        own = token_counts(usage, where)
        parts = [(None, model, own)]
        own_parts = []
        for part in usage.get('iterations') or []:
            kind = part.get('type') if isinstance(part, dict) else None
            if kind not in ITERATION_ROLES:
                raise ValueError(f'{where} has an unknown usage part: {kind!r}')
            if ITERATION_ROLES[kind]:
                parts.append((ITERATION_ROLES[kind], part.get('model') or 'unknown', token_counts(part, where)))
            else:
                own_parts.append(token_counts(part, where))
        if own_parts and [sum(values) for values in zip(*own_parts)] != own:
            raise ValueError(f"{where}: the message's parts do not add up to its usage")
        for role, part_model, counts in parts:
            if not any(counts):
                continue  # placeholder the client writes for a request that never reached the API
            row = rows.setdefault((role, part_model), [0] * (1 + len(TOKEN_FIELDS)))
            row[0] += 1
            for index, value in enumerate(counts, 1):
                row[index] += value
    return rows, stamps


def session_usage(session):
    """Token totals per role and model for a session transcript and its subagent transcripts."""
    session = Path(session)
    if not session.is_file():
        raise ValueError(f'No session transcript at {session}')
    sources = [('main', session)]
    for path in sorted((session.with_suffix('') / 'subagents').glob('agent-*.jsonl')):
        meta = path.with_name(path.stem + '.meta.json')
        role = 'unknown'
        if meta.is_file():
            role = json.loads(meta.read_text(encoding='utf-8')).get('agentType') or 'unknown'
        sources.append((role, path))
    totals = {}
    stamps = []
    for role, path in sources:
        rows, seen = transcript_usage(path)
        stamps += seen
        if role == 'main' and not any(part is None for part, _ in rows):
            raise ValueError(f'No assistant usage records in {session}; the transcript format may have changed')
        counted = set()
        for (part, model), counts in rows.items():
            key = (part or role, model)
            total = totals.setdefault(key, {'agents': 0, 'requests': 0, **dict.fromkeys(TOKEN_FIELDS, 0)})
            if key not in counted:
                counted.add(key)
                total['agents'] += 1
            total['requests'] += counts[0]
            for field, value in zip(TOKEN_FIELDS, counts[1:]):
                total[field] += value
    return totals, (min(stamps), max(stamps)) if stamps else None


def format_usage(totals, span):
    lines = ['| Who | Model | Agents | Requests | Input | Cache read | Cache write | Output |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    order = sorted(totals.items(), key=lambda item: (item[0][0] != 'main', -sum(item[1][field] for field in TOKEN_FIELDS)))
    for (role, model), row in order:
        cells = [role, model, row['agents'], f"{row['requests']:,}"] + [f'{row[field]:,}' for field in TOKEN_FIELDS]
        lines.append('| ' + ' | '.join(str(cell) for cell in cells) + ' |')
    if span:
        lines.append(f'First record {span[0]}, last record {span[1]}.')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('validate', help='check the skill, agents, role files and local links')
    installer = commands.add_parser('install', help='install the skill and agents into the Claude Code home')
    installer.add_argument('--home', type=Path, help='client home; defaults to CLAUDE_CONFIG_DIR or ~/.claude')
    installer.add_argument('--replace', action='store_true',
                           help='back up and replace installed files that differ')
    usage = commands.add_parser('usage', help='token totals per role for one Claude Code session')
    usage.add_argument('session', type=Path, help='path to the session .jsonl transcript')
    args = parser.parse_args()
    if args.command == 'usage':
        try:
            print(format_usage(*session_usage(args.session)))
        except (ValueError, OSError) as error:
            parser.exit(1, f'usage report failed: {error}\n')
    elif args.command == 'validate':
        try:
            count = validate()
        except (ValueError, OSError) as error:
            parser.exit(1, f'validate failed: {error}\n')
        print(f'Validated the skill, local links, and {count} agents.')
    else:
        home = args.home or default_home()
        try:
            count = install(home, replace=args.replace)
        except (ValueError, OSError) as error:
            parser.exit(1, f'install failed: {error}\n')
        print(f'Installed or confirmed {count} files in {home}.')


if __name__ == '__main__':
    main()
