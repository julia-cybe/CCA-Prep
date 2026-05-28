# Domain 2 Exercise 9: CLAUDE.md Hierarchy
CCA-F Topic: Claude Code Configuration & Workflows

---

## Key Concepts

### The 3-Level Hierarchy

Claude Code loads CLAUDE.md files from three scopes, merged in order (lower overrides higher):

```
1. User-level      ~/.claude/CLAUDE.md
                   → Personal preferences, personal shortcuts, your name, your style
                   → NOT version-controlled, NOT shared with the team
                   → Loaded for EVERY project on your machine

2. Project-level   <project-root>/CLAUDE.md
                   → Team standards, coding conventions, testing requirements
                   → Version-controlled, shared with every team member who clones
                   → Loaded for THIS project only

3. Directory-level <any-subdirectory>/CLAUDE.md
                   → Subsystem-specific rules (e.g., different conventions for /frontend)
                   → Version-controlled, scoped to files IN that directory
                   → Overrides parent CLAUDE.md for work in that subtree
```

**Load order**: user → project → directory (directory wins on conflicts)

---

### @import Syntax

Split large rule sets into focused files and import them:

```markdown
<!-- project-root/CLAUDE.md -->
@import .claude/rules/testing.md
@import .claude/rules/security.md
@import .claude/rules/api-conventions.md
```

- Imported files live in `.claude/rules/` (convention — any path works)
- Keeps the root CLAUDE.md concise; rules files stay focused
- All imported files are version-controlled alongside the project

---

### Path-Specific Rules (YAML frontmatter)

More token-efficient than creating directory-level CLAUDE.md files for every subsystem:

```markdown
---
globs: ["**/*.tf", "**/*.tfvars"]
---
# Terraform Rules
- Always use `terraform fmt` before committing
- Never hardcode resource names — use variables
- Tag every resource with `project` and `environment`
```

Use in the project-level CLAUDE.md or an imported file.
Rules only activate when Claude is working on files matching the glob — no wasted tokens otherwise.

**When to use directory CLAUDE.md vs. path-specific rules:**

| Situation | Better choice |
|-----------|---------------|
| Rules apply to a whole subtree with many file types | Directory CLAUDE.md |
| Rules apply only to a specific file extension/pattern | Path-specific (glob) rules |
| 50-line Terraform block that only matters for `.tf` files | Path-specific rules — saves tokens |
| Frontend component standards for `/frontend/**` | Directory CLAUDE.md in `/frontend/` |

---

### Exam Trap: Where Should the Rule Live?

The single most common exam trap: a rule that SHOULD be in project-level ends up in user-level — and a new team member never sees it.

**Decision questions:**
1. "Does every team member need this?" → project-level (or directory-level)
2. "Is this personal to me on my machine?" → user-level
3. "Does this apply only to files in one subsystem?" → directory-level or path-specific glob
4. "Is it a large rule set for a specific file type?" → path-specific rules (more efficient)

---

## Exercise

### Setup

Create this mock project structure (plain directories and files — no real code needed):

```
mock-project/
├── CLAUDE.md                   ← project-level
├── .claude/
│   └── rules/
│       ├── testing.md
│       └── terraform.md
├── frontend/
│   └── CLAUDE.md               ← directory-level
└── infra/
    └── main.tf                 ← (empty placeholder)
```

### Step 1 — Project-level CLAUDE.md

Write `mock-project/CLAUDE.md`:

```markdown
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
```

### Step 2 — Imported rule files

Write `mock-project/.claude/rules/testing.md`:

```markdown
## Testing Standards
- All tests use pytest (never unittest)
- Minimum 80% line coverage required
- Each public function must have at least one test
- Use fixtures over setUp/tearDown
```

Write `mock-project/.claude/rules/terraform.md`:

```markdown
## Terraform Standards
- Always run `terraform fmt` before committing
- Never hardcode resource names — use variables
- Tag every resource with `project` and `environment`
- Store state in S3 backend (never local)
```

### Step 3 — Directory-level CLAUDE.md

Write `mock-project/frontend/CLAUDE.md`:

```markdown
## Frontend Standards
- Framework: React 18 with TypeScript
- Use functional components only (no class components)
- CSS: Tailwind only — no inline styles
- Components live in src/components/, hooks in src/hooks/
```

### Step 4 — The "new team member" test

Now imagine a rule that should be shared sits in the WRONG place.

**Buggy state**: move "All tests use pytest" to your `~/.claude/CLAUDE.md` (user-level) instead of the project file.

Ask yourself:
- Sam clones the repo fresh. Does she see the pytest rule?
- Answer: NO — it's in your personal `~/.claude/CLAUDE.md`, not committed.
- Fix: move it to `mock-project/.claude/rules/testing.md` (project-level, version-controlled).

### Step 5 — Verify your mental model

Without running any code, answer these questions before looking at the reflection section:

1. Which files from the mock project above get committed to git?
all files within the mock-project
2. Which file does NOT get committed?
the user-level claude file
3. When Claude works on `infra/main.tf`, which rule sets activate?
terraform rules + testing ruleset
4. When Claude works on `frontend/App.tsx`, which rule sets activate? 
testing ruleset
5. If user-level and project-level both define a `## Testing` section, which wins?
-> project-level

**Expected answers:**
1. Everything under `mock-project/` — all CLAUDE.md files, all `.claude/rules/` files
2. `~/.claude/CLAUDE.md` — lives outside the repo
3. Project-level CLAUDE.md + terraform.md (glob match on `*.tf`) — but NOT frontend/CLAUDE.md
4. Project-level CLAUDE.md + testing.md (always active) + frontend/CLAUDE.md (directory match)
5. Project-level wins over user-level (directory-level would win over both)

---

## Concept Cheat Sheet

```
Scope           Location                    Shared?   When active
──────────────  ──────────────────────────  ────────  ──────────────────────────────
User-level      ~/.claude/CLAUDE.md         NO        All projects on your machine
Project-level   <root>/CLAUDE.md            YES       This project only
Directory-level <subdir>/CLAUDE.md          YES       Files in that subtree
Path-specific   glob rules in any CLAUDE.md YES       Files matching the glob pattern
Imported files  .claude/rules/*.md          YES       When @import'd by a CLAUDE.md
```

---

## Reflection Questions

Answer these in `learnings.md` after completing the exercise.

1. Your team has a rule "always write tests in pytest." Where should it live and why?

2. A rule "my name is Julia, always address me by name" — where does this belong?

3. You have 50 lines of Terraform rules that only apply to `.tf` files. What's more
   efficient: a directory-level CLAUDE.md in `/infra/` or path-specific glob rules?
   Why?

4. What does `@import` let you do, and where are the imported files typically stored?

5. A new developer joins and says Claude ignores all the team standards. What is the
   most likely cause, and how do you fix it?
