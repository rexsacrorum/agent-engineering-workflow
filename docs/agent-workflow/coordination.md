# Engineering coordination

Main owns scope, decisions, integration, and completion. Explicit user instructions and authorization take precedence. Apply this workflow in opted-in projects or when explicitly requested.

## Establish scope

Read target AGENTS.md (in Claude Code also CLAUDE.md), applicable nested instructions, and the project profile. Verify the absolute checkout and Git remote. Preserve the user's selected checkout and all pre-existing changes. Record acceptance criteria, authorization, base, HEAD, task-owned paths, and existing staged/unstaged changes in a local task record outside tracked source. Never include secrets or unrelated diff contents.

Give each substantial task its own session. Everything a session has read is sent again with every later request, so a second task pays for the first one's history. The task record and the pull request carry what the next session needs; the record follows the [template](../../templates/task-record.md) and lives where the template says, so a later session in the same clone finds it. When the user brings a new substantial task into a session that has already finished one, do the task, and mention once in that session that a fresh session would cost less. Do not wait for an answer and do not repeat it. Follow-up work on the same task stays in its session, and a task that takes several pull requests is one task.

Before implementation, decide whether the work can be implemented and verified coherently in one pass. Keep a small bounded task in one pass. Split a large, risky, or cross-component change into slices described by behavior, each with its criteria, dependencies, and checks. Write, review, and verify each slice under the ownership rules below, and commit it separately when commits are authorized; do not wait until all code is written to discover a gap in verification. Each slice is one change for the role rules below: its shape decides its reviewer, and the limit on reviews counts per slice. Then run the relevant checks on the combined result; it gets a new review only when integration changed code after the slices were reviewed. A passing slice does not complete the task.

Keep package paths separate from target paths. Shared tools may point at another workspace; verify their root and coordinate switches. Tool selection, commands, database safety, UI verification, and project specialists come from the target profile and repository instructions.

A project profile extends this contract and can replace its defaults for roles, model limits, evidence gates, and delivery procedures. User instructions and actual authorization still govern actions. Read linked project policies when they apply. A project may ship a wrapper skill that loads this workflow with a fallback profile for checkouts that lack one. Such a profile retains its own reference root; it never changes the task checkout or common package root.

## Select roles

Use only roles that materially help. Choose by the shape of the task, not by its size alone:

| Task shape | Who writes | Who else is called |
| --- | --- | --- |
| Small edit in one area, outside the risks named below | Main | Nobody. A specialist would spend more rebuilding context than the edit costs. |
| Substantial change in one area | Main, or one implementer when the contract fits in a few lines | One fresh reviewer on the finished diff. |
| Several independent parts on disjoint paths | One implementer per part, in parallel | One fresh reviewer on the combined diff. |
| Follow-up in an area an implementer already built | The same implementer, continued | A fresh reviewer when the follow-up is substantial. |
| Change of any size to access rights, a data migration, or anything that spends money | As above | A reviewer always, with that risk named as its first priority. |
| Risky stage ahead, such as sign-in, accounts, or payments | Nobody yet | QA architect once, on the plan for the stage. Main reads the files the design depends on and decides; a decision that is hard to reverse goes to the advisor. |
| Browser checks, long test runs, log reading | Nobody | Verifier. |
| Open-ended search: where a flow lives, across many files | Nobody | The client's search agent on the mid tier. Main keeps the lookup of a known symbol or string. |
| Watching a long run: replay, deployment, retries | Nobody | A token-free wait where the client has one; otherwise a watcher on the cheap tier. |
| Documentation or other bulk mechanics from a finished diff | Docs, or main for a few lines | Nobody. |
| Hard question | Nobody | Advisor; see [below](#escalate-a-hard-question). |

Main keeps planning, contested design decisions, and any edit that depends on what it just found. Writes stay single-threaded within an area: parallel implementers are allowed only on paths that do not overlap and do not depend on each other's unfinished work.

Skip a role when its condition holds:

| Role | Tier | Skip it when |
| --- | --- | --- |
| Reviewer | Strong | The edit is small, in one area, and touches no access rights, migration, or spending. |
| QA architect | Strong | The stage carries no unusual risk. It is a per-stage read, not a per-change checkpoint. |
| Implementer | Strong; mid when the contract is clear and the area is routine | The change depends on what main just found, or the contract cannot be written in a few lines. |
| Verifier | Mid | The check is one command with short output. A check with longer output may stay with main only as the last step of the session. A browser session always goes to the verifier. |
| Docs | Mid | The writer can make the documentation change in the same diff. |
| Watcher | Cheap | The client can wait for the run without tokens. |
| Delivery | Cheap | The client can wait for CI without tokens: commit, push, and PR are a few commands with small output, so main does them. |
| Advisor | Top | The decision is easy to reverse and the evidence does not conflict. |

Delegation pays when the output is large and many requests follow it, because everything main reads stays in its history and is re-read by every later request. It loses when the specialist must first rebuild context main already has. A specialist does not produce a better answer than main would for the same task; call one for parallel work, to keep bulky output out of main's history, or for a reader who has not seen how the code was written.

A project's profile says whether it has adopted the [output-trimming hook](../../templates/hooks/README.md). Where it has, main may run a test or build command itself when the hook covers it: one plain command, on the hook's list, through the Bash tool. Such a command returns only its last lines and the path of the full output. A command the hook does not cover, such as one with `&&`, a variable set in front, or one run through PowerShell, is not trimmed. Without the hook, or outside what it covers, a run with long output goes to the verifier.

A token-free wait means the client tells the session when a run ends without the session polling: a CI monitor that wakes the session, or a background command that notifies on exit. It is a property of the client in use, not of the project. The watcher only reports the outcome; main diagnoses a failure or assigns it.

A reviewer is never reused, because it has seen the reasoning. Main checks small repairs against the findings itself. A repair that is substantial, or that touches the named risk, gets one new reviewer, which reads the repair and the findings it answers, not the whole change again. Stop after that second review: main decides the remaining findings and reports the ones left open. The one exception is a defect in the named risk found by the second review; its repair is reviewed again. No role supervises other roles.

The search agent is the client's own, Explore in Claude Code, and not a role of this package. Give it the question, ask for conclusions with file and line and not file contents, and pass the mid tier as the model. It counts toward the limit of active specialists. Where the client has no such agent, main searches itself.

Choose how to find code by the kind of question. A question about a known symbol, such as where it is defined or who calls it, goes to a semantic tool or a direct read in whichever agent has the question: the answer is exact and small, so delegating it costs more than asking. A text or file-name search with a known pattern is a direct search. An open-ended question, such as how a feature flows across layers or where a change would land, goes to the search agent. A design decision is not a search: main reads the few files it depends on, because a summary loses the detail a decision needs.

The watcher has no wiring of its own. Give the verifier role file to a subagent at the cheap tier, with an assignment limited to waiting, reading the result, and reporting it. A mid-tier implementer is the implementer role with the tier lowered the same way. The four tiers are named in [tool wiring](tools.md); apply a tier other than the role's default only through a supported runtime override.

The common roles are implementer, reviewer, verifier, qa_architect, docs, and delivery, plus the advisor described below. Their instructions live in `roles/workflow_*.md` under the shared [specialist rules](roles/specialist.md); each client's wiring file holds the model defaults, as described in [tool wiring](tools.md). Do not duplicate model defaults in prose. Main retains the current session model unless the user requests otherwise. Preserve explicit model and budget limits.

When a profile names project replacements, use those role files and their settings for the corresponding duties. Do not launch both common and project roles for the same assignment. Give every specialist the common package root, selected profile and reference root, and target checkout. Read project role references from the project root and common role references from the common root. A profile can request a coordinator default, but runtime controls determine whether it can be applied.

At most three specialists are active, subject to the runtime limit. Specialists do not delegate, even where the client permits nested subagents. Continue an existing implementer, verifier, or docs writer where its context remains useful. Select the named role when available and its runtime settings match its wiring file. Otherwise pass its role file to a default subagent with the wiring file's model and effort as supported overrides; use fresh context when required by the runtime. Supply the package path, target path, scope, evidence, and ownership. If settings cannot be applied, report the limitation and continue locally or with a supported alternative; do not claim a model changed because instructions say so.

Each assignment states objective, acceptance criteria, target checkout, baseline, relevant paths and evidence, exclusions, allowed actions, resource ownership, required output, and a directory outside tracked source for bulky evidence. Reports follow the size limit in the [specialist rules](roles/specialist.md). Project-specific specialists follow the same ownership contract and specialist rules, including the report size limit, whether or not their role files link them.

## Escalate a hard question

Main may consult the advisor without separate confirmation when evidence conflicts, when an architecture, security, concurrency, or migration decision is hard to reverse, or when the same failure survives two repairs. Ask once per stage: one bounded question with the evidence and the options already considered. The advisor recommends; main decides and returns to the role defaults. Explicit user model and budget limits still apply. In Claude Code the advisor is `workflow_advisor`. A client without such a role gives the question to its strongest supported setting within the project's model limits. When the session already runs on the advisor's model, the advisor still gives a reader with fresh context, which helps most with conflicting evidence; say in main's final report that it was not a stronger model.

The client's own advisor tool is a different thing from the advisor role. Each call sends the caller's whole conversation to the advisor model without caching, so its price grows with the length of the session. This contract does not limit main's use of it. Specialists follow the limit in the [specialist rules](roles/specialist.md).

## Ownership and evidence

Grant source ownership of any path to one writer at a time, including main. Parallel implementers each own a disjoint set of paths, named in their assignments. Source includes tests, scripts, docs, and metadata. Transfer ownership explicitly; main does not edit concurrently with its writer. Readers may investigate a changing checkout, but final review and verification require a stable snapshot.

Stop source edits before review and verification. Capture HEAD, separate staged/unstaged binary diffs, and the paths and content hashes of non-ignored untracked files. Store evidence outside tracked source; record relevant ignored inputs separately. Give reviewer and verifier the same snapshot and compare it again after they finish. HEAD alone is insufficient in a dirty checkout. Unexpected edits invalidate affected evidence; reconcile with the owner rather than reset.

Only the verification owner runs tests, builds, browser mutations, or shared services during verification. Reviewer and QA architect remain read-only. Track shared roots, ports, containers, outputs, and child processes. Before repairs, wait for affected readers to finish and for verification processes to stop. An interrupt request alone does not release resources.

Collect findings, then assign each repair to the writer that owns those paths. Correct causes and simplify affected code without unrelated cleanup. Necessary refactors are within feature scope unless they cross explicit exclusions or another owner's paths. Report larger unrelated issues with evidence and a proposed scope. Repeat affected checks on the new stable snapshot; do not create separate concurrent repair loops.

## Completion

Use [verification](verification.md), [delivery](delivery.md), and optionally [knowledge](knowledge.md). When the project keeps a task log, add its line afterwards, as described in [measurement](measurement.md). Main resolves acceptance criteria, review findings, and required evidence. Record accepted deferred work in the project's tracked plan or an authorized issue, not only in chat or an external knowledge store. Do not invent issues solely for ceremony.

A request can cover less than its task. Judge the run against the criteria it covers, and the task against every line of the [task record](../../templates/task-record.md). A criterion this run does not cover stays open. Deferred is only for a criterion the user accepted as out of scope, recorded where the task record says. Give the reviewer, the QA architect, and the verifier the whole list with the criteria of this run marked, and name the open criteria at the top of main's final report.

Report what changed, verification results and limits, unresolved findings, and delivery state. Distinguish local, pushed, merged, and released. If delegation is unavailable, state that review was not independent. A missing knowledge store does not block work supported by repository evidence.
