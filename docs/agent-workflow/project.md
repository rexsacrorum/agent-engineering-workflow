# Project profile of this repository

Scope: a reusable engineering workflow for coding agents: the coordination contract, role definitions, client wiring, and the install, validation and usage helper.

Checks: `python scripts/workflow.py validate` and `python -m unittest discover -s tests`. There is no application UI or database, so browser testing does not apply.

A substantial change to the coordination contract or the roles gets an independent read-only scenario review: give a fresh reviewer concrete task scenarios and ask where the contract is ambiguous or contradicts itself. A change of any size to what the installer may write or replace gets an independent reviewer.

No task log is kept in this repository, and no external knowledge store is used.
