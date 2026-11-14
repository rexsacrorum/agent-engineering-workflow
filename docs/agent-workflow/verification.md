# Verification

Select checks from acceptance criteria, actual risks, repository instructions, and CI. Do not invent universal commands. User-facing changes need the project's browser/manual evidence; backend-only changes may use API, unit, integration, and runtime evidence as appropriate. Honor backup and isolated-database requirements before any test that may mutate data.

Before a risky stage, QA architecture maps its requirements to evidence once, on the plan. It assesses final results after verification only when that plan named evidence that is costly or easy to skip; otherwise the reviewer reports missing coverage. It plans and assesses; the verifier executes. A project profile can require more. Missing evidence must identify the affected requirement and whether the limit is acceptable. Main resolves insufficient coverage or clearly reports the outstanding gap.

Run required checks against the stable snapshot supplied to independent review. Record command, exit status, observed behavior, environment, and artifact references. A green unit suite does not establish browser behavior or installed-package compatibility. Run expensive checks only when a concrete risk or project policy calls for them.

After a repair, repeat affected checks and reassess coverage. Do not repeat unrelated suites merely to accumulate evidence. Stop child processes and release shared resources before transferring ownership. Report failures to main without editing source during verification.
