# Project workflow profile

Adapt this file in the target repository as `docs/agent-workflow/project.md`. Retain existing authoritative instructions rather than copying them.

- Canonical repository identity and relevant components.
- Links to AGENTS.md, specs, architecture, and delivery conventions.
- Supported navigation/runtime tools and fallback conditions.
- Build, test, browser, and environment prerequisites; database/media backup rules.
- Domain-specific agents and when their expertise is needed. A project role that only reads gets `disallowedTools: Write, Edit, NotebookEdit` in its agent file, like the common ones.
- Acceptance evidence and explicit completion requirements.
- Changes that always get an independent reviewer (access rights, migrations, spending) and stages whose requirements main maps to evidence before work starts.
- How a session waits for CI when the client in use cannot wait without tokens, and the project's own delivery role when it has one.
- Where task records live, when the default in the workflow package's `templates/task-record.md` does not fit, and whether the project uses the task-record hook from `templates/hooks/`.
- Whether the project uses the output-trimming hook from the workflow package's `templates/hooks/`, and its command list when the default does not fit.

## Task log

State whether the project keeps the task log from the common measurement policy and where: by default a tracked `docs/agent-workflow/task-log.md`. A public repository may keep it outside tracked source.

## Knowledge store

An external knowledge store is off unless this section turns it on. When it is on, name the store, which decisions, procedures and findings are worth saving, the exclusions, how stale notes are handled, and whether any standing write authorization exists. Without explicit authorization, reading does not authorize writing.
