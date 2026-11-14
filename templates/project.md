# Project workflow profile

Adapt this file in the target repository as `docs/agent-workflow/project.md`. Retain existing authoritative instructions rather than copying them.

- Canonical repository identity and relevant components.
- Links to AGENTS.md, specs, architecture, and delivery conventions.
- Supported navigation/runtime tools and fallback conditions.
- Build, test, browser, and environment prerequisites; database/media backup rules.
- Domain-specific agents and when their expertise is needed.
- Acceptance evidence and explicit completion requirements.
- Changes that always get an independent reviewer (access rights, migrations, spending) and stages that get one architecture and QA read of the plan.
- Which role delivers when the client in use cannot wait for CI without tokens.

## Task log

State whether the project keeps the task log from the common measurement policy and where: by default a tracked `docs/agent-workflow/task-log.md`. A public repository may keep it outside tracked source.

## Knowledge store

An external knowledge store is off unless this section turns it on. When it is on, name the store, which decisions, procedures and findings are worth saving, the exclusions, how stale notes are handled, and whether any standing write authorization exists. Without explicit authorization, reading does not authorize writing.
