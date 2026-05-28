# Domain 2 Exercise 11: CI/CD Integration with Claude Code
CCA-F Topic: Claude Code Configuration & Workflows

---

## Key Concepts

### The `-p` Flag: Non-Interactive Mode

By default, Claude Code is interactive — it waits for user input, asks clarifying questions, and prompts for confirmation before taking actions.

In CI/CD, there is no user. If Claude waits for input, the pipeline hangs forever (or until timeout).

The `-p` flag (short for `--print`) switches Claude Code to **non-interactive mode**:
- Sends a single prompt and exits when done
- Never waits for user input
- Returns a non-zero exit code on failure (pipeline-compatible)
- Compatible with `--output-format json` for structured output

```bash
# WRONG — hangs in CI because Claude waits for input
claude "Review this PR for security issues"

# RIGHT — exits cleanly after one pass
claude -p "Review this PR for security issues"
```

**Without `-p`**: Pipeline hangs → CI timeout → false failure
**With `-p`**: Claude runs, outputs result, exits with code 0 or 1

---

### Structured Output for CI Parsing

`--output-format json` makes Claude's output machine-parseable. Combine it with `-p`:

```bash
claude -p "Review PR #$PR_NUMBER for issues" \
  --output-format json \
  > review_output.json
```

The JSON output includes:
- `result`: Claude's response text
- `cost_usd`: token cost for the run
- `stop_reason`: why Claude stopped (`end_turn`, etc.)

For **strict structured output**, pair with a JSON schema (tool_use pattern under the hood):

```bash
claude -p "Extract findings from the diff" \
  --output-format json \
  --json-schema '{"type":"object","properties":{"findings":{"type":"array","items":{"type":"object","properties":{"severity":{"enum":["high","medium","low"]},"file":{"type":"string"},"description":{"type":"string"}},"required":["severity","file","description"]}}}}' \
  > findings.json

# Parse with jq downstream
HIGH=$(jq '[.findings[] | select(.severity=="high")] | length' findings.json)
if [ "$HIGH" -gt 0 ]; then
  echo "::error::$HIGH high-severity findings — blocking merge"
  exit 1
fi
```

---

### Independent Review Instance vs. Self-Review

A model reviewing its own output is less reliable than an independent instance reviewing it fresh.

**Why self-review fails:**
- The model that wrote the code already committed to a mental model of how it works
- It tends to confirm its own assumptions rather than challenge them
- It looks for the bugs it *expected* might exist, not the ones it *didn't anticipate*

**Why independent review catches more:**
- Fresh context: no prior commitment to the implementation choices
- Reads the code as a reviewer, not as the author
- More likely to notice logic gaps the author glossed over

**In CI, independent review means:**
- A separate `claude -p` invocation that receives the diff/PR as input
- Does NOT have access to the conversation where the code was written
- Acts as a second pair of eyes, not a self-check

---

### Plan Mode

Plan Mode (`claude --plan` or toggling in the UI) makes Claude **show its plan before acting**.

Claude describes what it intends to do — which files to edit, which commands to run, what the overall approach is — and waits for approval before executing anything.

**Use Plan Mode when:**
- The action is irreversible: deleting files, dropping tables, force-pushing
- The scope is large: refactoring many files, schema migrations
- You need sign-off: compliance or change-management requirements
- You are uncertain: the task is ambiguous and you want to verify Claude's interpretation before it acts

**Do NOT use Plan Mode in CI:**
- CI is non-interactive — Plan Mode pauses and waits for human approval
- Use `-p` (non-interactive) for CI and reserve Plan Mode for interactive developer workflows

**Decision rule:**
```
Is a human available to review the plan before execution?
  YES → Plan Mode is appropriate
  NO  → Use -p (non-interactive), Plan Mode will hang
```

---

### Documenting Testing Standards in CLAUDE.md for CI

When Claude Code runs in CI, it loads CLAUDE.md just like it does locally. This means the same standards apply — but only if they are in version-controlled project-level CLAUDE.md.

**Why CLAUDE.md instead of CI pipeline YAML:**

| CLAUDE.md | Pipeline YAML |
|-----------|--------------|
| Loaded by Claude automatically | Must be explicitly passed as a flag or prompt |
| Version-controlled alongside code | Separate maintenance burden |
| Available to local dev sessions too | CI-only — dev runs don't see it |
| Stays in sync with the code it governs | Can drift from codebase conventions |

**Example**: If `CLAUDE.md` says "all tests use pytest", Claude in CI will apply that standard when reviewing test files — without the pipeline needing to know about it.

The pattern from `mock-project/CLAUDE.md` already does this: `@import .claude/rules/testing.md` means every Claude instance — local and CI — sees the testing standards automatically.

---

## Exercise

### Step 1 — Add a CI section to the project CLAUDE.md

Update `mock-project/CLAUDE.md` to add a CI/CD section so Claude knows how to behave when invoked in CI:

```markdown
## CI/CD Behavior
- When reviewing PRs: output findings as structured JSON
- Severity thresholds: block merge on any "high" severity finding
- Never request user input — operate non-interactively
- Review scope: changed files only (not full codebase)
```

This ensures the CI-invoked Claude instance applies the right review behavior without the pipeline YAML having to encode it.

---

### Step 2 — Version 1: the broken CI workflow (hangs)

This is what a naive CI workflow looks like. Understand WHY it breaks:

```yaml
# .github/workflows/broken-review.yml
name: PR Review (broken)

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Claude Code
        run: npm install -g @anthropic-ai/claude-code

      - name: Review PR
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          # WRONG: no -p flag → Claude waits for user input → pipeline hangs
          claude "Review PR #${{ github.event.pull_request.number }} for issues"
```

**What happens**: Claude starts, outputs a greeting or asks a clarifying question, then waits. The pipeline times out after 6 hours (GitHub Actions default). The PR is blocked with a misleading timeout error.

---

### Step 3 — Version 2: the correct CI workflow

```yaml
# .github/workflows/pr-review.yml
name: PR Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # need full history for diff

      - name: Install Claude Code
        run: npm install -g @anthropic-ai/claude-code

      - name: Get PR diff
        run: |
          git diff origin/${{ github.base_ref }}...HEAD > pr_diff.txt

      - name: Review PR with Claude
        id: claude_review
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          claude -p "$(cat <<'EOF'
          Review the following PR diff for issues. Apply the project testing standards from CLAUDE.md.

          $(cat pr_diff.txt)

          Output ONLY a JSON object matching this structure:
          {"findings": [{"severity": "high|medium|low", "file": "...", "line": 0, "description": "..."}]}
          EOF
          )" \
            --output-format json \
            > raw_output.json

          # Extract Claude's response text (the JSON findings)
          jq -r '.result' raw_output.json > findings.json

      - name: Enforce severity threshold
        run: |
          HIGH=$(jq '[.findings[] | select(.severity=="high")] | length' findings.json)
          MEDIUM=$(jq '[.findings[] | select(.severity=="medium")] | length' findings.json)

          echo "High severity findings: $HIGH"
          echo "Medium severity findings: $MEDIUM"

          # Post findings as PR comment (GitHub CLI)
          gh pr comment ${{ github.event.pull_request.number }} \
            --body "$(jq -r '.findings[] | "[\(.severity | ascii_upcase)] \(.file):\(.line) — \(.description)"' findings.json)"

          # Block merge on high severity
          if [ "$HIGH" -gt 0 ]; then
            echo "::error::Blocking merge: $HIGH high-severity finding(s)"
            exit 1
          fi
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Key differences from Version 1:**
- `-p` flag: non-interactive, exits cleanly
- `--output-format json`: structured, parseable output
- `jq` downstream: extract findings and enforce threshold
- `exit 1` on high severity: fails the check, blocks merge

---

### Step 4 — Verify your mental model

Answer these before reading the reflection section:

1. You run `claude "check this code"` in GitHub Actions. What happens?
2. An independent CI review instance has `context: fork` behavior — it can't see the author's conversation. Is this a bug or a feature?
3. A team lead wants Claude to plan its changes before touching production infra. Which mode and which flag?
4. Where do your testing standards need to live so the CI Claude instance sees them automatically?
5. Your pipeline passes but outputs garbled JSON. What flag is missing?

**Expected answers:**
1. The pipeline hangs — Claude waits for user input that never arrives, eventually timing out
2. Feature — isolation means no author bias; Claude reviews as a fresh reader
3. Plan Mode for the developer workflow; `-p` would skip planning (wrong for this use case — needs human approval)
4. In `CLAUDE.md` at project level (version-controlled) — CI Claude loads it automatically
5. `--output-format json` — without it, output is plain text, not parseable JSON

---

## Concept Cheat Sheet

```
Flag/Mode           Purpose                              CI-safe?
──────────────────  ───────────────────────────────────  ────────
-p / --print        Non-interactive mode, exits cleanly  YES — required
--output-format json  Machine-parseable JSON output      YES — recommended
--json-schema       Enforce strict output structure       YES
Plan Mode           Show plan, wait for human approval   NO — waits for input

Pattern                       Use case
────────────────────────────  ──────────────────────────────────────────
-p + --output-format json     Standard CI review invocation
jq downstream                 Parse findings, enforce thresholds
CLAUDE.md for standards       Auto-loaded by every Claude instance (local + CI)
Independent review instance   No author bias, catches more subtle issues
```

---

## Reflection Questions

Answer these in `learnings.md` after completing the exercise.

1. What does the `-p` flag do and what breaks without it in CI?

2. Why does an independent Claude review instance catch more subtle issues than
   self-review?

3. What output format should a CI Claude invocation use for downstream parsing?

4. In what type of situation should you engage Plan Mode instead of letting
   Claude execute directly?

5. Why put testing standards in CLAUDE.md instead of in the CI pipeline YAML?
