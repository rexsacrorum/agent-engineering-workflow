# Agent engineering workflow repository

Maintain reusable workflow mechanics here; project-specific policy belongs in the repository that adopts the workflow.

Use [engineering-workflow](skills/engineering-workflow/SKILL.md) for substantial changes and read [this project profile](docs/agent-workflow/project.md). Small standalone edits remain direct, except a change to what the installer may write or replace, which gets an independent reviewer at any size.

Validate with `python scripts/workflow.py validate` and `python -m unittest discover -s tests`. Keep examples and instructions free of credentials and machine-specific paths.

Keep role instructions in `docs/agent-workflow/roles/` and model defaults in the wiring files only ([tool wiring](docs/agent-workflow/tools.md)). Do not add repeated approval gates.
