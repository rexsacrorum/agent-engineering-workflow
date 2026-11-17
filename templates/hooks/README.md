# Output-trimming hook

`trim_output.py` is a Claude Code `PreToolUse` hook. It keeps the output of test and build commands out of the conversation, where every later request would read it again. The [coordination contract](../../docs/agent-workflow/coordination.md#select-roles) sends runs with long output to the verifier. With the hook, main may run the commands it covers itself, and the verifier's own runs are trimmed too.

The installer does not install it. A project adopts it by hand, only when requested.

## What it does

When an agent runs one plain command that starts with a listed runner, such as `pytest -q` or `npm test`, the hook rewrites the call. The whole output goes to a file. The agent sees the file's path first, then the last 60 lines and the exit status. The command's exit status is kept, so a failing run still fails. The command runs in a subshell, so a directory change or a variable it sets does not carry over to the next call.

Everything else passes unchanged: a command with pipes, redirections, several statements or substitutions, a background command, a PowerShell call, and a command that is not on the list. The hook never approves or blocks a call.

## Adopt it

1. Copy `trim_output.py` to `.claude/hooks/trim_output.py` in the project. It needs Python 3.11 or later and nothing else. It works on Windows with Git Bash, on Linux and on macOS, in bash and in zsh.
2. Add the hook to the project's `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {"type": "command", "command": "python \"${CLAUDE_PROJECT_DIR}/.claude/hooks/trim_output.py\""}
        ]
      }
    ]
  }
}
```

On macOS and Linux the interpreter is usually `python3`, and `python` may not exist: write `python3` in the command there. On Windows write `python`. A project used on both keeps the command in each developer's `.claude/settings.local.json`.

3. Run a test command in a new session and check that the result starts with `[full output:` and ends with a line that starts with `[exit`.

## Settings

Set these as environment variables, for example under `env` in the same settings file.

| Variable | Meaning | Default |
| --- | --- | --- |
| `WORKFLOW_TRIM_COMMANDS` | Comma-separated command prefixes. Replaces the built-in list. | Common test and build runners; see `DEFAULT_COMMANDS` in the script. |
| `WORKFLOW_TRIM_LINES` | How many last lines to show. | 60 |
| `WORKFLOW_TRIM_DIR` | Where the output files go. A relative path is taken from the directory the command runs in. | The session's scratchpad directory when the client names one, otherwise a directory of the user's own under the system temp directory. |

## Limits

- It covers the Bash tool only. Commands run through the PowerShell tool are not trimmed.
- It covers one plain command. `cd app && npm test` and `CI=1 pytest` pass unchanged.
- In auto mode the client can refuse a call whose input a hook changed, because it reviewed the original. The agent then sends the rewritten command again as it was shown, which costs one extra step for that command.
- When the output file cannot be created, the command runs unchanged.
- The output files are not cleaned up by the hook. In the session's scratchpad the client removes them with the session.
- A runner that prints its failures first and a long summary last can push the failure out of the shown lines. The path to the full output is always printed; search that file for the failure and do not read it whole.
