# Authorized delivery

Honor the user's current and prior publication scope. Prepare a concrete, reviewed result before asking for any genuinely missing authorization. A request for a PR includes its normal branch, commits, push, and description; it does not itself authorize merging or deployment. Repository creation and initial publication can be performed when requested without inventing a PR requirement.

Verify remote, branch, index, and task-owned changes before every publication. Grant one Git mutation owner. Stage only assigned changes and preserve unrelated staged and unstaged work. Use the project's branch, commit, and PR conventions; otherwise use a short descriptive task branch. Never reset another task's work.

The PR should explain the concrete problem, resulting behavior, validation, and material limits. External comments and review requests require user authorization or an explicitly invoked workflow that authorizes those particular actions; this generic workflow does not grant blanket messaging permission.

Inspect CI and review for the exact pushed revision. Queued jobs remain pending. Return failures to main for coordinated repairs, then verify the updated revision. Prefer notifications or bounded checks and report outstanding jobs honestly; do not claim green results or approval for stale revisions. No merge, release, infrastructure restart, or deployment beyond the authorized task.
