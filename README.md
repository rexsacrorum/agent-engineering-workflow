# Agent engineering workflow

A small, opinionated workflow for coding agents: when the main agent should delegate, to which role, on which model tier, what a role may send back, and how to measure whether any of it pays. It ships as plain Markdown plus one Python helper, with wiring for Claude Code.

It was extracted from daily use on several private projects. The rules are grounded in published evidence and in one measured session; [evidence](docs/evidence.md) says which is which and what was not verified.

## The rules in one screen

1. **Choose roles by the shape of the task, not its size.** A small edit needs nobody. A substantial change gets one writer and one fresh reviewer. Independent parts on disjoint paths get parallel writers.
2. **Writes stay single-threaded.** One writer per set of paths at a time, main included.
3. **A reviewer is always fresh and never reused.** It has not seen how the code was written; that is the point.
4. **Some changes are reviewed at any size:** access rights, data migrations, anything that spends money.
5. **Every role has a condition under which it is not worth calling.** A specialist that must first rebuild context main already has costs more than it saves.
6. **Keep bulky output out of the main agent's history.** Everything main reads is re-read by every later request. Test runs, browser checks and logs go to a verifier on a cheaper tier, which returns one line per check and a path to the full output.
7. **Reports are short.** About 300 words plus findings; evidence goes to a file.
8. **Waiting should cost nothing.** Use the client's own notification for long runs; otherwise a watcher on the cheapest tier.
9. **One substantial task per session.** A second task pays for the first one's history on every request. A short task record and the pull request carry what the next session needs.
10. **Measure, because felt speed is not evidence.** One line per task, a read-only usage report, and a periodic review that proposes instruction changes for a person to accept.

The full text is the [coordination contract](docs/agent-workflow/coordination.md).

## What one measured session showed

One long session, 23 pull requests, main on the top tier and specialists on the strong tier, priced at list price:

| Who | Share of cost |
| --- | --- |
| Main agent | about half; more than half of that was re-reading its own history |
| Advisor-tool calls | about a quarter |
| Implementers | about a sixth |
| Eight independent reviews | about 6%, under $3 each before the advisor calls some of them made |

It is one session with no comparison run. It shows where tokens went, not that another split would have been cheaper. Details and caveats are in [evidence](docs/evidence.md#one-measured-session).

## Contents

- [engineering-workflow](skills/engineering-workflow/SKILL.md): the skill that routes a task into the workflow.
- [coordination](docs/agent-workflow/coordination.md): delegation rules, ownership, escalation, completion.
- [roles](docs/agent-workflow/roles): role instructions, written once.
- [.claude/agents](.claude/agents): thin wiring that owns model defaults; see [tool wiring](docs/agent-workflow/tools.md).
- [verification](docs/agent-workflow/verification.md), [delivery](docs/agent-workflow/delivery.md), [knowledge](docs/agent-workflow/knowledge.md), [measurement](docs/agent-workflow/measurement.md).
- [project template](templates/project.md): the profile a participating repository adapts.
- [task record](templates/task-record.md): the shape of the per-task record that carries a task from one session to the next.
- [output-trimming hook](templates/hooks/README.md): an optional Claude Code hook that keeps test and build output out of the conversation. The installer does not install it.
- [evidence](docs/evidence.md): sources, the measured session, and a reading list.

## Install

Python 3.11 or later, standard library only.

```
python scripts/workflow.py validate
python scripts/workflow.py install
```

`install` copies the skill and the `workflow_*` agents into the Claude Code home (`CLAUDE_CONFIG_DIR`, default `~/.claude`). Installed files point back to this checkout, so keep it available. A differing installed file is refused unless `--replace` is given, which backs it up first. `--home <directory>` installs somewhere else. The installer refuses to write through a symbolic link or junction inside the client home. The command does not edit your settings or any project.

The installer does not delete anything. A role removed from the package stays in the client home until it is deleted by hand: after an update that drops a role, delete its file under `agents/` there. The roles dropped so far are `workflow_architecture`, `workflow_qa_architect`, `workflow_docs`, and `workflow_delivery`.

Open a new session after installing so the roles are discovered.

## Adopt in a project

1. Copy [templates/project.md](templates/project.md) to `docs/agent-workflow/project.md` in the project and fill it in: checks, shared resources, the changes that always get a reviewer, and whether the project keeps a task log.
2. Route to it from the project's instructions, for example in `CLAUDE.md`:

   > For substantial tasks use the `engineering-workflow` skill with the project profile in `docs/agent-workflow/project.md`. Keep small standalone edits direct, except a change to access rights, a data migration, or spending, which gets an independent reviewer at any size.

   Put the exception in the routing line itself. A small edit does not load the skill, so a rule that lives only inside the skill never reaches it.
3. A wrapper is a small project skill that loads this one with the project's own profile. A project needs one only when it replaces the common roles with its own, or needs a fallback profile for checkouts that lack one. Otherwise the common skill and the profile are the whole workflow.

## Measure

```
python scripts/workflow.py usage <session.jsonl>
```

prints token totals per role and model for one Claude Code session, from the session transcript and its subagent transcripts. It counts each API message once and reports advisor calls as their own row, split by the role that called. It also prints file-editing calls per role and what the main agent's history is made of. It stops with an error when a usage record does not have the shape it expects, because the transcript format is internal to the client and can change.

```
python scripts/workflow.py sessions --since <date>
```

prints a summary of the same counts as one row per session on this machine, for the task log. Both commands only read.

[Measurement](docs/agent-workflow/measurement.md) describes the task log and the periodic review.

## Limits

- The cost numbers come from one session, and the knowledge-store counts from the stored sessions of one developer's machine.
- No controlled experiment isolating the effect of a fresh-context reviewer was found; the published numbers are vendor reports.
- Wiring is provided for Claude Code only. The rules do not depend on the client; the tiers must be mapped to another client's models by hand.

## License

[MIT](LICENSE).
