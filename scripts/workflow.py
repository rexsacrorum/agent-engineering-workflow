"""Validate or install this workflow package, report whether the installation is current, or report a session's
token usage and file edits.

Python 3.11+, standard library only.
"""

import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess


PACKAGE = Path(__file__).resolve().parents[1]
ROLES = {'implementer', 'reviewer', 'verifier', 'advisor'}
MODELS = {'opus', 'sonnet', 'haiku', 'fable', 'inherit'}
EFFORTS = {'low', 'medium', 'high', 'xhigh', 'max'}
# Roles that only read. Their wiring must deny the editing tools, so the client enforces it.
READ_ONLY = {'reviewer', 'advisor'}
# MultiEdit is an older name: it appears in old transcripts and is not a tool to deny today.
EDITING_TOOLS = {'Write', 'Edit', 'NotebookEdit'}
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
        # One line, with or without brackets and quotes. A list over several lines is not read.
        denied = set(re.findall(r'\w+', fields.get('disallowedTools', '')))
        if path.stem.removeprefix('workflow_') in READ_ONLY and not EDITING_TOOLS <= denied:
            raise ValueError(f'{path} is a read-only role: write `disallowedTools: '
                             f"{', '.join(sorted(EDITING_TOOLS))}` on one line of its frontmatter")
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


def git(package, *arguments):
    try:
        # No optional locks, so `git status` does not rewrite the index. No prompt, so a fetch cannot wait for one.
        done = subprocess.run(['git', '--no-optional-locks', '-C', str(package), *arguments], capture_output=True,
                              timeout=60, encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL,
                              env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def remote_default(package):
    listed = git(package, 'ls-remote', '--symref', 'origin', 'HEAD') or ''
    found = re.match(r'ref: refs/heads/(\S+)\s+HEAD', listed)
    return f'origin/{found.group(1)}' if found else None


def commits(count):
    return '1 commit' if count == '1' else f'{count} commits'


def checkout_state(package, fetch=False):
    """Describe the package checkout. Installed files point back to it, so its revision is the installed version.

    The second value is True when the checkout has every commit of the remote default branch, False when it is
    behind, and None when the two could not be compared.
    """
    revision = git(package, 'rev-parse', '--short', 'HEAD')
    if revision is None:
        return [f'Package: {package.as_posix()} is not a Git checkout, so its revision is unknown.'], None
    branch = git(package, 'branch', '--show-current') or 'no branch'
    lines = [f'Package: {package.as_posix()} at {revision} ({branch})']
    current = True
    fetched = fetch and git(package, 'fetch', '--quiet', 'origin') is not None
    if fetch and not fetched:
        lines.append('  could not fetch from origin; the comparison below uses the last fetch')
    # A fetch does not move the local origin/HEAD, so after one ask the remote which branch is its default.
    main = ((fetched and remote_default(package)) or git(package, 'rev-parse', '--abbrev-ref', 'origin/HEAD')
            or 'origin/main')
    behind = git(package, 'rev-list', '--count', f'HEAD..{main}')
    ahead = git(package, 'rev-list', '--count', f'{main}..HEAD')
    when = 'fetched now' if fetched else 'as of the last fetch; pass --fetch to ask the remote'
    if behind is None or ahead is None:
        current = None
        lines.append(f'  {main} is not known here, so this revision is not compared with the remote')
    elif behind == '0' and ahead == '0':
        lines.append(f'  same revision as {main} ({when})')
    else:
        if behind != '0':
            current = False
            lines.append(f'  {commits(behind)} behind {main} ({when}): update this checkout')
        if ahead != '0':
            lines.append(f'  {commits(ahead)} not on {main}: roles read rules from this unmerged work')
    # Tracked files only: an untracked folder beside the package, such as a tool's cache, changes no rule.
    if git(package, 'status', '--porcelain', '--untracked-files=no'):
        lines.append('  uncommitted changes to tracked files: roles read rules from them as they are now')
    return lines, current


def installed_state(home, package=PACKAGE):
    """Compare the installed files with what `install` would write now. Reads only."""
    package = Path(package).resolve()
    # As in `install`: the home itself may be reached through links; links inside it are refused.
    try:
        destination = Path(home).expanduser().resolve()
    except (RuntimeError, OSError):
        destination = Path(home).expanduser().absolute()
    writes = planned_writes(destination, package)
    lines = [f'Installed in {destination.as_posix()}:']
    current = True
    for path, content in sorted(writes.items()):
        name = path.relative_to(destination).as_posix()
        try:
            inside = (path, *path.parents[:len(path.relative_to(destination).parts) - 1])
            if any(is_link(parent) for parent in inside):
                state = 'linked'
            elif not path.exists():
                state = 'missing'
            elif not path.is_file():
                state = 'blocked'
            else:
                found = path.read_bytes()
                state = 'current' if found == content else 'differs'
                if state == 'differs' and path.name == 'package-root.txt':
                    name += f" (names another checkout: {found.decode('utf-8', errors='replace').strip()})"
        except OSError as error:
            state = 'unread'
            name += f' ({error.strerror or error})'
        current = current and state == 'current'
        lines.append(f'  {state:8} {name}')
    for path in sorted((destination / 'agents').glob('workflow_*.md')):
        if path not in writes:
            current = False
            lines.append(f'  {"stale":8} {path.relative_to(destination).as_posix()} '
                         '(the package has no such role now, and `install` does not remove it)')
    return lines, current


def status(home, package=PACKAGE, fetch=False):
    package = Path(package).resolve()
    checkout, checkout_current = checkout_state(package, fetch)
    installed, installed_current = installed_state(home, package)
    lines = checkout + installed
    if not installed_current:
        lines.append('Not current. `install --replace` backs up and rewrites missing and differing files. '
                     'It refuses a linked path and one that is not a file (blocked), and it leaves a stale role '
                     'file in place: move those away by hand.')
    elif checkout_current is None:
        lines.append('The installed files match this checkout. Its revision was not compared with a remote.')
    elif not checkout_current:
        lines.append('The installed files match this checkout, and the checkout is behind.')
    else:
        lines.append('Current.')
    return '\n'.join(lines), installed_current and checkout_current is not False


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


def transcript_records(path):
    """Yield (location, record) for each line of a Claude Code transcript."""
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
            yield where, record


def transcript_usage(path):
    """Sum one Claude Code transcript into {(role or None, model): [requests, *tokens]}.

    The format is not a public interface, so anything unexpected raises instead
    of producing a partial count."""
    messages = {}
    stamps = []
    for where, record in transcript_records(path):
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


class NoUsage(ValueError):
    """The main transcript holds no request: a session that was opened and left, or an unknown format."""


def session_sources(session):
    """The session transcript as 'main', then each subagent transcript with its role."""
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
    return sources


def session_usage(session):
    """Token totals per role and model for a session transcript and its subagent transcripts.

    Advisor calls get rows of their own, one per calling role."""
    totals = {}
    stamps = []
    for role, path in session_sources(session):
        rows, seen = transcript_usage(path)
        stamps += seen
        if role == 'main' and not any(part is None for part, _ in rows):
            raise NoUsage(f'No assistant usage records in {session}; the transcript format may have changed')
        counted = set()
        for (part, model), counts in rows.items():
            key = (f'{part}, called by {role}' if part else role, model)
            total = totals.setdefault(key, {'agents': 0, 'requests': 0, **dict.fromkeys(TOKEN_FIELDS, 0)})
            if key not in counted:
                counted.add(key)
                total['agents'] += 1
            total['requests'] += counts[0]
            for field, value in zip(TOKEN_FIELDS, counts[1:]):
                total[field] += value
    return totals, (min(stamps), max(stamps)) if stamps else None


WRITE_TOOLS = {'Edit', 'Write', 'MultiEdit', 'NotebookEdit'}
SUBAGENT_TOOLS = {'Agent', 'Task'}
HISTORY_PARTS = ('tool calls', 'tool output', 'messages, client notes and subagent reports', "the agent's own text")


def text_length(content):
    """Characters of text in a message's content. Images and other non-text parts count as zero."""
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(part['text']) for part in content
                   if isinstance(part, dict) and part.get('type') == 'text' and isinstance(part.get('text'), str))
    return 0


def transcript_activity(path):
    """Count file-editing calls in one transcript and the characters its conversation is made of.

    Only 'assistant' and 'user' records are read. The client also stores copies of its requests
    in records of other types, some without a timestamp; they repeat calls already counted here.
    A call or a result that appears on more than one line is counted once, by its id."""
    edits = 0
    history = dict.fromkeys(HISTORY_PARTS, 0)
    calls = {}
    results = set()
    for _, record in transcript_records(path):
        message = record.get('message')
        kind = record.get('type')
        if kind not in ('assistant', 'user') or not isinstance(message, dict):
            continue
        content = message.get('content')
        if isinstance(content, str):
            content = [{'type': 'text', 'text': content}]
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get('type') == 'text':
                part = "the agent's own text" if kind == 'assistant' else 'messages, client notes and subagent reports'
                history[part] += text_length([block])
            elif block.get('type') == 'tool_use' and kind == 'assistant' and block.get('id') not in calls:
                calls[block.get('id')] = block.get('name')
                history['tool calls'] += len(json.dumps(block.get('input'), ensure_ascii=False))
                edits += block.get('name') in WRITE_TOOLS
            elif block.get('type') == 'tool_result' and kind == 'user' and block.get('tool_use_id') not in results:
                results.add(block.get('tool_use_id'))
                reported = calls.get(block.get('tool_use_id')) in SUBAGENT_TOOLS
                part = 'messages, client notes and subagent reports' if reported else 'tool output'
                history[part] += text_length(block.get('content'))
    return edits, history


def session_activity(session):
    """File-editing calls per role, and what the main agent's history is made of, in characters."""
    edits = {}
    history = None
    for role, path in session_sources(session):
        count, parts = transcript_activity(path)
        edits[role] = edits.get(role, 0) + count
        if role == 'main':
            history = parts
    return edits, history


def format_activity(edits, history):
    order = sorted(((role, count) for role, count in edits.items() if count),
                   key=lambda item: (item[0] != 'main', -item[1], item[0]))
    lines = ['File-editing calls: ' + (', '.join(f'{role} {count:,}' for role, count in order) or 'none') + '.']
    total = sum(history.values())
    if total:
        shares = ', '.join(f'{part} {round(100 * history[part] / total)}%' for part in HISTORY_PARTS)
        lines.append(f"Main's history by characters: {shares}. This covers the whole transcript, "
                     'including what a compaction later replaced; images, thinking and attachments are not counted.')
    return '\n'.join(lines)


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


def project_name(session):
    """The project a session worked in, from the working directory its records name."""
    for _, record in transcript_records(session):
        if isinstance(record.get('cwd'), str) and record['cwd']:
            parts = PurePosixPath(record['cwd'].replace('\\', '/')).parts
            for index in range(len(parts) - 1):
                if parts[index:index + 2] == ('.claude', 'worktrees'):  # a worktree of the project
                    parts = parts[:index]
                    break
            return parts[-1] if parts and parts[-1] != '/' else session.parent.name
    return session.parent.name


def session_row(session):
    """One log row for a session, from the same counts the usage report prints."""
    totals, span = session_usage(session)
    if not span:
        raise ValueError(f'No timestamps in {session}')
    edits, history = session_activity(session)

    def millions(count):
        return f'{count / 1_000_000:.2f}'

    def listed(counts):
        return ', '.join(f'{name} {value}' for name, value in sorted(counts.items(), key=lambda item: -item[1])) or 'none'

    main_rows = [row for (role, _), row in totals.items() if role == 'main']
    advisor = {}
    output = {}
    for (role, _), row in totals.items():
        if role.startswith('advisor, called by '):
            caller = role.removeprefix('advisor, called by ')
            advisor[caller] = advisor.get(caller, 0) + row['requests']
        else:
            output[role] = output.get(role, 0) + row['output_tokens']
    started = {}
    for role, _ in session_sources(session)[1:]:
        started[role] = started.get(role, 0) + 1
    first, last = (datetime.fromisoformat(stamp.replace('Z', '+00:00')) for stamp in span)
    used = sum(history.values())
    requests = sum(row['requests'] for row in main_rows)
    return {
        'first': span[0],
        'last': span[1],
        'requests': requests,
        'cells': [
            span[0][:10], project_name(session), session.stem[:8],
            f'{(last - first).total_seconds() / 3600:.1f}',
            f'{requests:,}',
            millions(sum(row['cache_read_input_tokens'] for row in main_rows)),
            ', '.join(f'{role} {millions(count)}' for role, count in
                      sorted(output.items(), key=lambda item: -item[1])) or 'none',
            listed(started),
            listed(advisor),
            listed({role: count for role, count in edits.items() if count}),
            f"{round(100 * (history['tool calls'] + history['tool output']) / used)}%" if used else 'none',
        ],
    }


SESSION_COLUMNS = ('Started (UTC)', 'Project', 'Session', 'Hours from first to last record', 'Main requests',
                   'Main cache read, M', 'Output by role, M', 'Subagents started', 'Advisor calls',
                   'File-editing calls', "Tool calls and output in main's history")


def sessions_table(home, since=None, project=None, least=20):
    """A Markdown table of the sessions under a Claude Code home, oldest first.

    A session is listed when its last record is on or after `since` (a UTC date) and its main
    agent made at least `least` requests. A session with no request at all is passed over. A
    transcript that cannot be read is counted and never stops the table."""
    rows = []
    unreadable = small = 0
    for session in sorted((Path(home) / 'projects').glob('*/*.jsonl')):
        try:
            # A file last written more than a day before the date holds no later record.
            if since and date.fromtimestamp(session.stat().st_mtime).toordinal() < since.toordinal() - 1:
                continue
            if project and project.lower() not in project_name(session).lower():
                continue
            row = session_row(session)
        except NoUsage:
            continue
        except Exception:  # whatever one transcript holds, the others are still listed
            unreadable += 1
            continue
        if since and row['last'][:10] < since.isoformat():
            continue
        if row['requests'] < least:
            small += 1
            continue
        rows.append((row['first'], row['cells']))
    lines = ['| ' + ' | '.join(SESSION_COLUMNS) + ' |', '|' + ' --- |' * len(SESSION_COLUMNS)]
    lines += ['| ' + ' | '.join(cells) + ' |' for _, cells in sorted(rows)]
    lines.append(f'{len(rows)} sessions listed; {small} with fewer than {least} main requests left out; '
                 f'{unreadable} transcripts could not be read.')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('validate', help='check the skill, agents, role files and local links')
    installer = commands.add_parser('install', help='install the skill and agents into the Claude Code home')
    installer.add_argument('--home', type=Path, help='client home; defaults to CLAUDE_CONFIG_DIR or ~/.claude')
    installer.add_argument('--replace', action='store_true',
                           help='back up and replace installed files that differ')
    state = commands.add_parser('status', help='whether the installed files match this checkout; reads only')
    state.add_argument('--home', type=Path, help='client home; defaults to CLAUDE_CONFIG_DIR or ~/.claude')
    state.add_argument('--fetch', action='store_true',
                       help='fetch from origin first, so the comparison with its default branch is up to date')
    usage = commands.add_parser('usage', help='token totals and file edits per role for one Claude Code session')
    usage.add_argument('session', type=Path, help='path to the session .jsonl transcript')
    sessions = commands.add_parser('sessions', help='one log row per Claude Code session, for the task log')
    sessions.add_argument('--since', type=date.fromisoformat, help='only sessions with a record on or after this date')
    sessions.add_argument('--project', help='only sessions whose project name contains this text')
    sessions.add_argument('--least', type=int, default=20, help='leave out sessions with fewer main requests')
    sessions.add_argument('--home', type=Path, help='Claude Code home; defaults to CLAUDE_CONFIG_DIR or ~/.claude')
    args = parser.parse_args()
    if args.command == 'sessions':
        print(sessions_table(args.home or default_home(), args.since, args.project, args.least))
    elif args.command == 'usage':
        try:
            print(format_usage(*session_usage(args.session)))
            print(format_activity(*session_activity(args.session)))
        except (ValueError, OSError) as error:
            parser.exit(1, f'usage report failed: {error}\n')
    elif args.command == 'status':
        text, current = status(args.home or default_home(), fetch=args.fetch)
        print(text)
        parser.exit(0 if current else 1)
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
