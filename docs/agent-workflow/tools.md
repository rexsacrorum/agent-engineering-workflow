# Tool wiring

Role instructions live once, in [roles](roles/). The client gets a thin wiring file per role that names the role, its model and effort, and points at the role file. Edit instructions in `roles/`; edit models only in the wiring files.

This package ships wiring for Claude Code:

- Role wiring: `.claude/agents/workflow_*.md`, with `model` and `effort` in the frontmatter, and `disallowedTools` for the roles that only read.
- Installed to `~/.claude/agents/` and `~/.claude/skills/engineering-workflow/` by `python scripts/workflow.py install`.
- Repository instructions: CLAUDE.md. When a repository has both CLAUDE.md and AGENTS.md, Claude Code reads only CLAUDE.md by default, so import the other file there with a line `@AGENTS.md` or put the routing in CLAUDE.md. It reads AGENTS.md by itself only when no CLAUDE.md exists.
- Advisor: `workflow_advisor`.

The installer records `package-root.txt` beside the installed skill, so a role can find its file when main did not pass the package path. `--replace` moves differing installed files to `<home>/workflow-backups/<time>/` before writing.

For another client, write the same thin wiring in that client's format, map the four tiers below to its models, and keep the role files unchanged.

## Model choices

The [coordination contract](coordination.md#select-roles) names four tiers and leaves the models to this file. A tier is chosen by what a mistake in the role costs and by how much the role reads compared with how much it decides.

| Tier | Claude Code | Used for |
| --- | --- | --- |
| Top | Fable | The advisor only. |
| Strong | Opus | Roles that judge or own correctness. |
| Mid | Sonnet | Roles that read much and decide little; an implementer working from a clear contract in a routine area. |
| Cheap | Haiku | Waiting, publishing, and reading results. |

The defaults, role by role:

- The reviewer, which judges correctness, and the implementer, which owns it, run on Opus at high effort.
- Docs, verifier, and QA architect run on Sonnet. Docs needs careful writing (high). The verifier mostly runs commands, and QA planning maps evidence and runs nothing (medium); the reviewer on the strong tier still reports missing coverage.
- Delivery is mechanical Git and CI reading, so it runs on Haiku at medium; main keeps failure diagnosis. Where the client can wait for CI without spending tokens, main delivers and the role is not called.
- The roles that only read (reviewer, QA architect, advisor) carry `disallowedTools: Write, Edit, NotebookEdit` in their wiring, so the client withholds the file-editing tools from them whatever the prompt says. They keep the shell and every other tool, so this closes the direct way to change a file and not every way. A role file passed to a default subagent, as the coordination fallback allows, carries no such denial.
- A watcher or a mid-tier implementer has no wiring file. Main passes the verifier or implementer role with the lower model as a runtime override: the `model` argument of a subagent call in Claude Code. If the client cannot apply it, the role runs at its default and main reports that.
- The advisor runs on Fable at high. The top tier costs several times more per token and a turn can take minutes, so it is an [escalation step](coordination.md#escalate-a-hard-question), called for one question at a time.

Effort is always explicit because the default differs between models. Aliases (`opus`, `sonnet`, `haiku`, `fable`) follow the current model generation; pin a full model ID only when a fixed version is required. A project profile can replace these defaults with its own roles.

In a long session, history re-read from cache on every request is the largest part of what main costs, and its price differs less between tiers than the price of output does. Moving a role down a tier saves less than keeping its output out of main; do both where the role allows.
