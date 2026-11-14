---
name: engineering-workflow
description: Coordinate substantial engineering work in opted-in repositories through scoped agents, independent review, verification, and authorized delivery.
---

Main owns planning, integration, and completion. Keep small standalone changes direct, except a change to access rights, a data migration, or spending: at any size it gets an independent reviewer as the coordination contract describes.

Resolve the package root from `package-root.txt` beside this skill when installed; otherwise it is two directories above this skill directory. The package is reference material, not the target checkout.

Read the package's `docs/agent-workflow/coordination.md` and the target repository's AGENTS.md (in Claude Code also CLAUDE.md) and `docs/agent-workflow/project.md` when present. A project wrapper may supply a verified fallback profile for a checkout that lacks one. Keep that profile's reference root separate from the target checkout and shared package root. If no profile exists, use existing repository instructions and report material missing requirements; do not invent commands or create a profile without task scope.

Select only useful `workflow_*` roles or the project's explicit replacements and specialists; the package's `docs/agent-workflow/tools.md` says where the client loads them. Apply the project's role selection, model limits, required evidence, and delivery rules over common defaults, within user authorization. Follow model settings through supported runtime controls and the coordination fallback. Delegate independent work for substantial tasks when it adds useful evidence. Specialists do not delegate.

Read `verification.md` for checking changes, `delivery.md` for authorized publication, and `knowledge.md` when a shared knowledge store would help. Resolve those files under the package's `docs/agent-workflow/`. Keep content selection and project-specific specialists in the target project.
