"""Claude Code PreToolUse hook: keep long test and build output out of the conversation.

Everything a command prints stays in the agent's history and is read again on every later
request. This hook rewrites a plain test or build command so that its whole output goes to a
file. The agent sees the file's path first, then the last lines and the exit status.

Only a Bash call that is one plain command starting with a listed runner is rewritten. A
command with pipes, redirections, several statements or substitutions passes unchanged, and so
does a background command, a PowerShell call, and any input the hook does not understand. The
command's exit status is kept. The hook never approves or blocks a call.

Settings, as environment variables:
  WORKFLOW_TRIM_COMMANDS  comma-separated command prefixes; replaces the default list
  WORKFLOW_TRIM_LINES     how many last lines to show (default 60)
  WORKFLOW_TRIM_DIR       where to write the output files; a relative path is taken from the
                          directory the command runs in (default: the session's scratchpad
                          directory when the client names one, otherwise a directory of this
                          user's own under the system temp directory)

Python 3.11+, standard library only.
"""

from datetime import datetime
import getpass
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys
import tempfile


DEFAULT_COMMANDS = (
    'npm test', 'npm run test', 'npm run build', 'pnpm test', 'pnpm build', 'yarn test', 'yarn build',
    'pytest', 'python -m pytest', 'python -m unittest', 'python3 -m pytest', 'python3 -m unittest',
    'go test', 'go build', 'go vet',
    'cargo test', 'cargo build', 'cargo clippy', 'dotnet test', 'dotnet build',
    'mvn', 'gradle', './gradlew', 'make', 'terraform plan',
)
DEFAULT_LINES = 60
# One plain command: no pipes, redirections, statement separators, substitutions, comments,
# grouping or line breaks. Anything else is left exactly as the agent wrote it.
PLAIN = re.compile(r'[^;&|<>`$#\\(){}\r\n]+')


def commands():
    listed = os.environ.get('WORKFLOW_TRIM_COMMANDS')
    if listed is None:
        return DEFAULT_COMMANDS
    return tuple(prefix.strip() for prefix in listed.split(',') if prefix.strip())


def shown_lines():
    try:
        return max(1, int(os.environ.get('WORKFLOW_TRIM_LINES', DEFAULT_LINES)))
    except ValueError:
        return DEFAULT_LINES


def matches(command, prefixes):
    command = command.strip()
    if not PLAIN.fullmatch(command):
        return False
    return any(command == prefix or command.startswith(prefix + ' ') for prefix in prefixes)


def fallback_directory():
    """A directory of this user's own under the system temp directory.

    Several users can share the system temp directory. A common name there would belong to
    whoever ran the hook first, and nobody else could write a log into it. Where there is no
    numeric user id (Windows), the name carries the user's name, with every character that is
    not a letter, a digit, a dot or a hyphen replaced: a name such as `R&D` would otherwise make
    a path that cannot go into the rewritten command."""
    try:
        owner = str(os.getuid()) if hasattr(os, 'getuid') else re.sub(r'[^\w.-]', '_', getpass.getuser())
    except Exception:
        owner = 'user'
    return Path(tempfile.gettempdir()) / f'claude-output-{owner}'


def claim(directory, private):
    """Create the output file, empty, and return its path; None when that cannot be done safely.

    The shell later writes into this file. Creating it here shows that this user can write
    there, so the redirection in the rewritten command does not fail before the command runs.
    A sandbox that lets the shell write less than this process can still stop it. A private
    directory is made for this user alone, and is refused when it is a link or belongs to
    someone else, because other users of a shared temp directory can guess its name."""
    if not PLAIN.fullmatch(directory.as_posix()) or '"' in directory.as_posix():
        return None  # a path that would not survive inside the rewritten command
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o777)
        if private:
            info = directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or (hasattr(os, 'getuid') and info.st_uid != os.getuid()):
                return None
        handle, name = tempfile.mkstemp(prefix=f'output-{datetime.now():%Y%m%d-%H%M%S}-', suffix='.log',
                                        dir=directory)
        os.close(handle)
    except OSError:
        return None
    return Path(name).as_posix()


def rewrite(command, path, lines):
    """The same command with its output in a file, the last lines printed and the exit status kept.

    The path is printed before the command starts, so it is known even when the run is cut short.
    The closing line follows an empty line, so it stands alone when the output has no final newline.
    The command runs in a subshell: zsh refuses a whole line when a pattern in it matches nothing,
    and the subshell keeps that refusal inside the redirected part, so its message is shown too."""
    quoted = shlex.quote(path)
    return (f'echo "[full output: {path}]"; ( {command.strip()} ) > {quoted} 2>&1; rc=$?; '
            f'tail -n {lines} {quoted}; echo; echo "[exit $rc; last {lines} lines shown]"; ( exit $rc )')


def decide(hook_input):
    """Return the hook's JSON answer for one hook input: a rewritten call, or {} for no change."""
    if not isinstance(hook_input, dict) or hook_input.get('tool_name') != 'Bash':
        return {}
    tool_input = hook_input.get('tool_input')
    if not isinstance(tool_input, dict) or tool_input.get('run_in_background'):
        return {}
    command = tool_input.get('command')
    if not isinstance(command, str) or not matches(command, commands()):
        return {}
    scratchpad = hook_input.get('scratchpad_dir')
    chosen = os.environ.get('WORKFLOW_TRIM_DIR') or (scratchpad if isinstance(scratchpad, str) else None)
    if chosen:
        # The shell that runs the command may be in another directory than this process.
        working = hook_input.get('cwd')
        directory = Path(working if isinstance(working, str) else '.', chosen).absolute()
    else:
        directory = fallback_directory().absolute()
    path = claim(directory, private=not chosen)
    if not path:
        return {}
    updated = {**tool_input, 'command': rewrite(command, path, shown_lines())}
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'updatedInput': updated}}


def main():
    try:
        # The client sends UTF-8. Read bytes, so that the platform's default encoding cannot change
        # the command; the answer is written as ASCII with escapes.
        answer = decide(json.loads(sys.stdin.buffer.read()))
    except Exception:  # whatever the input is, the call must go ahead unchanged
        answer = {}
    json.dump(answer, sys.stdout)


if __name__ == '__main__':
    main()
