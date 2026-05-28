# Project Standards

@import .claude/rules/testing.md

## General
- Language: Python 3.12+
- All functions must have type annotations
- Use `ruff` for linting before committing

---
globs: ["**/*.tf", "**/*.tfvars"]
---
@import .claude/rules/terraform.md

## CI/CD Behavior
- When reviewing PRs: output findings as structured JSON
- Severity thresholds: block merge on any "high" severity finding
- Never request user input — operate non-interactively
- Review scope: changed files only (not full codebase)
