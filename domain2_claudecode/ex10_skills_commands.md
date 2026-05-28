# Domain 2 Exercise 10: Custom Slash Commands & Skills
CCA-F Topic: Claude Code Configuration & Workflows

---

## Key Concepts

### Custom Slash Commands

A custom slash command is a Markdown file that Claude Code loads as an invokable prompt template.

```
Project-level    .claude/commands/<name>.md
                 → Version-controlled, shared with every team member
                 → Invoked as /<name> in the Claude Code session

Personal-level   ~/.claude/commands/<name>.md
                 → Personal only, NOT version-controlled
                 → Invoked as /<name> on your machine only
```

When you type `/<name>`, Claude Code reads the file and uses its content as the prompt for that turn.
You can pass an argument after the command name; the argument is injected where `$ARGUMENTS` appears in the file.

**Example**: `.claude/commands/review-pr.md`

```markdown
Review pull request $ARGUMENTS.

Check for:
- Logic errors and edge cases
- Missing tests
- Security issues (injection, auth bypass, secrets in code)
- Breaking changes to public API

Output a structured report with severity (high / medium / low) for each finding.
```

Invoked as: `/review-pr 42` → Claude reviews PR #42.

---

### Skills

A skill is a slash command with **frontmatter** that controls how Claude Code executes it.

```markdown
---
context: fork
allowed-tools: Grep, Read
argument-hint: <path-to-audit>
---

Audit the code at $ARGUMENTS for security vulnerabilities.

Focus on:
- Injection flaws (SQL, command, path traversal)
- Secrets or credentials hardcoded in source
- Insecure default configurations
- Overly permissive file access

Return a structured list of findings with file:line references.
```

#### Frontmatter fields

| Field | Purpose |
|-------|---------|
| `context: fork` | Run the skill as an **isolated subagent**. It gets its own context window and cannot read or modify the parent conversation. Protects main context from large skill outputs. |
| `allowed-tools` | Whitelist of tools the skill may use. Restricts blast radius. |
| `argument-hint` | Text shown next to the slash command in the UI to tell the user what argument to provide. |

#### `context: fork` — what it means in practice

Without `context: fork`:
- Skill runs in the SAME conversation context
- Its entire output (potentially huge for a security audit) lands in your main context
- Uses up tokens that your main conversation needs
- Previous conversation history is visible to the skill

With `context: fork`:
- Skill spawns a **separate Claude instance** (a subagent)
- Isolated context: it cannot see main conversation history
- Its output is returned as a single result block, not inline in the conversation
- Main context stays clean regardless of how much the skill outputs
- Exactly like spawning a subagent with the Task tool — same isolation model

**Rule**: Use `context: fork` whenever a skill might produce large outputs or should not have access to the full conversation history.

---

### Skills vs. CLAUDE.md vs. Slash Commands — Decision Table

| Need | Right tool |
|------|-----------|
| Rule that applies to EVERY interaction ("always use type annotations") | CLAUDE.md |
| On-demand task invoked explicitly by the user | Slash command or skill |
| On-demand task that returns large output and shouldn't pollute context | Skill with `context: fork` |
| On-demand task that needs restricted tool access | Skill with `allowed-tools` |
| On-demand task shared with the team | Project-level `.claude/commands/` |
| On-demand task personal to one developer | User-level `~/.claude/commands/` |

**Key distinction**: CLAUDE.md is *always loaded* (universal standards). Slash commands/skills are *invoked on demand* (task-specific actions).

---

### Exam Trap: Where Should the Command Live?

Same as CLAUDE.md — the most common trap is a shared command sitting in `~/.claude/commands/` where teammates can't see it.

**Decision rule:**
- "Does the whole team need this command?" → `.claude/commands/` (project-level, version-controlled)
- "Is this personal to me?" → `~/.claude/commands/` (user-level, not shared)

---

## Exercise

### Setup — directory structure to create

Inside `domain2_claudecode/mock-project/`, add:

```
mock-project/
├── CLAUDE.md                          ← already exists from Session 9
├── .claude/
│   ├── rules/                         ← already exists from Session 9
│   └── commands/
│       ├── review-pr.md               ← Step 1: project-level slash command
│       └── security-audit.md          ← Step 2: skill with context: fork
└── ...
```

---

### Step 1 — Create a project-level slash command

Create `mock-project/.claude/commands/review-pr.md`:

```markdown
Review pull request $ARGUMENTS.

Check for:
- Logic errors and edge cases that tests don't cover
- Missing or insufficient tests
- Security issues: injection, authentication bypass, secrets committed to code
- Breaking changes to public API surface

Output a structured report:
- **High**: must fix before merge
- **Medium**: should fix before merge
- **Low**: consider fixing, non-blocking

Group findings by severity. Include file:line references for each finding.
```

This command is now available to every team member as `/review-pr <PR-number>`.

---

### Step 2 — Create a skill with `context: fork`

Create `mock-project/.claude/commands/security-audit.md`:

```markdown
---
context: fork
allowed-tools: Grep, Read
argument-hint: <directory-or-file-to-audit>
---

Perform a security audit of the code at $ARGUMENTS.

Look for:
1. Injection vulnerabilities: SQL injection, command injection, path traversal
2. Hardcoded secrets or credentials (API keys, passwords, tokens)
3. Insecure defaults: debug mode enabled, permissive CORS, missing auth checks
4. Overly permissive file access or directory listing
5. Unvalidated external input reaching sensitive operations

For each finding, output:
- **Severity**: Critical / High / Medium / Low
- **Location**: file:line
- **Description**: what the vulnerability is
- **Recommendation**: how to fix it
```

---

### Step 3 — Observe the difference

**Without `context: fork`** (imagine removing it from the frontmatter):
- `/security-audit src/` runs inline in your current conversation
- The audit's full output (potentially hundreds of lines) fills your context
- Claude's next response has less context budget for your actual work
- The skill can read everything in the current conversation (potential info leak)

**With `context: fork`**:
- `/security-audit src/` spawns an isolated subagent
- Subagent only knows what's in the command file + your argument
- Subagent's full output comes back as a single summary in your chat
- Your main conversation context is unaffected
- Subagent can only use `Grep` and `Read` — it cannot write files or run code

---

### Step 4 — Verify your mental model

Answer these before reading the reflection section:

1. Sam clones the repo. Which commands are available to her immediately?
both, review pr and security audit 
2. You add `/standup` to `~/.claude/commands/standup.md`. Does Sam see it?
no, as this is a user-level command
3. The security-audit skill has `allowed-tools: Grep, Read`. Can it edit a file?
no
4. A junior dev runs `/security-audit` on a 20,000-line codebase. Does this break the main conversation's context budget?
No because the skill includes a context fork
5. You want `/review-pr` to show "PR number" as a hint in the UI. What frontmatter field do you add?
argument-hint: <pr-number>

**Expected answers:**
1. Both `review-pr` and `security-audit` — they are in `.claude/commands/` (project-level, version-controlled)
2. No — `~/.claude/commands/` is personal and not committed to the repo
3. No — `allowed-tools` is a whitelist; Edit and Write are not listed
4. No — `context: fork` isolates it in a subagent; main context is unaffected
5. `argument-hint: <PR-number>` in the skill's frontmatter

---

## Concept Cheat Sheet

```
Command type     Location                        Shared?   Frontmatter?
───────────────  ──────────────────────────────  ────────  ────────────
Slash command    .claude/commands/<name>.md       YES       NO
Slash command    ~/.claude/commands/<name>.md     NO        NO
Skill            .claude/commands/<name>.md       YES       YES (context/tools/hint)
Skill            ~/.claude/commands/<name>.md     NO        YES

context: fork    → isolated subagent, clean main context
allowed-tools    → whitelist of tools the skill may use
argument-hint    → UI hint for what argument to pass
$ARGUMENTS       → where user-supplied argument is injected into the prompt
```

---

## Reflection Questions

Answer these in `learnings.md` after completing the exercise.

1. What is the difference between a custom slash command and a skill?

2. Why would you set `context: fork` on a skill?

3. A skill needs the PR number as input. Which frontmatter field do you use to
   hint to the user what to type?

4. Should "always use 4-space indentation" live in a skill or CLAUDE.md? Why?

5. A teammate has a personal slash command `/standup` they want to share with
   the team. Where should it be moved and what (if anything) needs to change?
