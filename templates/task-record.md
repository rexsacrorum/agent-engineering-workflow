# Task record

One file per substantial task, however many branches or pull requests the task takes. It is what the next session reads; the pull request carries the rest. Leave out secrets and the contents of unrelated changes.

Keep it where Git never tracks it: by default `task-records/<name>.md` inside the repository's Git directory (`git rev-parse --git-common-dir`), which every worktree of the clone shares. The name is the branch the task started on, or a short task name when there is no branch; it stays the same when the branch is renamed or the task moves to another branch. Name the record in the pull request description. Another clone or a cloud session does not have the file; there the pull request is what carries the task. A project profile can name another place, for example when the client asks for approval before each write to the Git directory.

## Task

The request in one or two sentences. What is authorized: commit, push, merge. Base and HEAD commits and the branch, the paths this task owns, and the changes that were already in the checkout.

## Acceptance criteria

One line per criterion, each with a status: open, done, deferred (and where that is recorded), or moved to another task. The task is complete when no line is open. Before a risky stage, add to each of its criteria the evidence that will show it.

## Decisions

Each decision with the fact that decided it. Rejected options in one line each. Documents in a shared knowledge store that were read or written, by ID.

## Evidence

Checks run, with their results and the path of the full output. Review findings and what was done about each.

## Delivery and resumption

Commit, branch, pull request and CI state, and whether the work is local, pushed or merged. What remains, in order. When resuming, compare this record with the live Git and remote state first; where they differ, Git is right.
