# Measurement

The workflow costs tokens and attention. This loop shows whether it pays for them. It reads what already exists and adds one line per task. The reasoning and sources are in the [evidence](../evidence.md).

## Task log

A project opts in through its profile and keeps the log in a tracked file, by default `docs/agent-workflow/task-log.md`. Main adds one line for each completed substantial task. Small edits are not logged.

The line is never added to the branch of a PR under review. Add it after the task's PR merges, as a small documentation commit of its own. Fill the token fields then, while the session is at hand. Write "pending" for what is not known yet; the periodic review completes those fields from the PRs.

| Field | Source |
| --- | --- |
| Date, PR or commit | Main |
| Task shape, from the table in [coordination](coordination.md#select-roles) | Main |
| Roles called, with tier or model | The usage report below |
| Tokens by role: cache read, cache write, output | The usage report below |
| Wall time from first prompt to PR | The usage report's first and last record, or PR timestamps |
| Review findings by severity, and how many were accepted | Reviewer report |
| Defects the reviewer missed that a bot, CI, or the user found | PR comments and checks |
| CI failures before merge | PR checks |
| Corrections and redirections by the user during the task | Main |
| Follow-up fix or revert within 14 days | Git history; filled in at the periodic review |
| A read from the knowledge store changed a decision: yes, no, not used | Main |

Write "not measured" for a field that was not checked. Do not estimate. Keep secrets, customer data, and transcript excerpts out of the log.

## Usage report

`python scripts/workflow.py usage <session.jsonl>` prints token totals for one Claude Code session, one row per role and model: main, each subagent type from the session's subagent transcripts, and advisor calls, which the transcript records apart from the message that made them. The advisor row is the client's own advisor tool, which main and specialists can call; it is not the `workflow_advisor` role, which appears as a subagent row. A role run on another model appears as a second row. A role file given to a default subagent appears under that subagent's type. For the advisor row, the agents column counts the transcripts that called it. Claude Code stores sessions under its configuration directory, in `projects/<project>/<session>.jsonl`.

The command only reads. It counts each API message once, and stops with an error when a usage record does not have the shape it expects, because the transcript format is internal to the client and can change between versions. It prints tokens, not money: multiply by the current price list when a cost is needed, and call the result a list-price equivalent unless the work was billed per token.

When one session holds several tasks, the report covers all of them. Log the session's line against the tasks it covered, or start substantial tasks in their own sessions.

Two alternatives need no script. The client's built-in `/usage` breakdown shows the subagent share of a session. Its OpenTelemetry export separates main from subagent usage and suits a team that already runs a collector. Other clients have no usage report here; log their token fields as "not measured".

## Periodic review

The user starts the review, weekly or after about five new lines when work is slower; main may suggest it when it sees that many unreviewed lines. Main first completes the pending fields from the PRs. It then gives a fresh mid-tier subagent the new log lines and the PRs they name, with their review comments. It returns at most three proposed instruction changes. Each names the file, the changed text, the observation behind it, and what later log lines would show if it helped.

Main does not apply these proposals. They go to the user as a diff. This keeps a person in the loop and stops instruction files from growing with every task.

## Reading the numbers

- A few tasks a week give small, noisy counts. Compare tasks of the same shape.
- Change one rule at a time, and note the date in the log.
- Do not turn a count into a target. A reviewer asked to find problems always finds something. A review rule earns its place when it finds defects that would otherwise reach merge.
- One session shows where tokens went. It does not show that another split would have been cheaper.
