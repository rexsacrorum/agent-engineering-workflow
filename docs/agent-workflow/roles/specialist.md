# Specialist rules

These apply to every `workflow_*` role and to project roles that link here.

- Read the package's [coordination contract](../coordination.md), then the target repository's AGENTS.md (in Claude Code also CLAUDE.md), nested instructions, and project profile.
- Work in the absolute target checkout from the assignment. The package path is reference material. Coordinate shared tool roots before switching them.
- Do not delegate. Main owns planning and completion. Act only within the ownership and authorization main assigns.
- Writers are not alone in the checkout: preserve other edits and release ownership explicitly.
- Return results, evidence, changed paths or "no edits", snapshot identity, limitations, and the required next action.
- Keep the report to main within about 300 words plus the list of findings. Main re-reads everything you return on every later request. Write logs, screenshots, full command output, and long excerpts to the evidence directory from the assignment, outside tracked source, and give the paths. A role that only reads has no file-editing tool: it cites file and line in place of a long excerpt. Do not restate the assignment or the diff, and do not narrate the work.
- The client's advisor tool, where it is on, sends your whole conversation to the top model on every call. Only the role that writes the change may call it, whether it is the common implementer or a project's own writer. It may call once per assignment: before committing to an approach when the assignment leaves a design choice open, or when the same failure has survived two repairs. Do not call it before reporting; a fresh reviewer reads the result. Every other role does not call it.
- Propose notes for a shared knowledge store to main; do not write shared memory yourself.
