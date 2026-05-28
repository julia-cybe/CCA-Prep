# Claude Certified Architect (CCA) — Foundations: Complete Guide

## Naming & Overview

The certification is the **Claude Certified Architect (CCA) — Foundations** (abbreviated **CCA-F**). It is NOT "Claude Certified Associate." It launched **March 12, 2026** and is the first tier of Anthropic's planned credential stack.

---

## Exam At a Glance

| Attribute | Detail |
|-----------|--------|
| Questions | 60 |
| Question type | Multiple choice, scenario-based (1 correct + 3 distractors) |
| Time limit | 120 minutes, single proctored session, no breaks |
| Passing score | 720 / 1,000 (scaled 100–1,000) |
| Code writing | NOT required — tests architecture decisions, not syntax |
| Guessing penalty | None — answer every question |
| Results | Within 2 business days + digital badge |
| Proctoring | ProctorFree (online) — no external tools, no Claude, no docs |

### Scenario-based structure
The exam randomly selects **4 of 6 possible production scenarios**. Every question is anchored to those 4 scenarios.

The 6 possible scenarios are:
1. **Customer Support Resolution Agent** — returns, billing disputes, account issues; 80%+ first-contact resolution target
2. **Code Generation with Claude Code** — acceleration via code generation, refactoring, debugging
3. **Multi-Agent Research System** — coordinator + specialized subagents for web research, analysis, synthesis
4. **Developer Productivity with Claude** — codebase exploration, boilerplate, routine task automation
5. **Claude Code for CI/CD** — automated code reviews, test generation, pull request feedback
6. **Structured Data Extraction** — information extraction from unstructured docs with JSON schema validation

---

## Exam Domains and Weightings

| # | Domain | Weight |
|---|--------|--------|
| 1 | Agentic Architecture & Orchestration | **27%** |
| 2 | Claude Code Configuration & Workflows | **20%** |
| 3 | Prompt Engineering & Structured Output | **20%** |
| 4 | Tool Design & MCP Integration | **18%** |
| 5 | Context Management & Reliability | **15%** |

Domain 1 is the largest because "it is the domain that breaks the most things in production."

---

## Domain 1: Agentic Architecture & Orchestration (27%)

### Agentic loop control
- Loop continues when `stop_reason = "tool_use"`; terminates when `stop_reason = "end_turn"`
- **Anti-patterns**: parsing natural language signals ("I'm done"), using arbitrary iteration caps, checking text content as a completion indicator

### Multi-agent hub-and-spoke orchestration
- Coordinator at center; subagents NEVER communicate directly with each other
- Coordinator handles: task decomposition, agent selection, context passing, result aggregation, error handling

### Subagent context passing
- Subagents do **NOT** automatically inherit the coordinator's conversation history
- Every needed piece of information must be explicitly included in the subagent's prompt
- Use the Task tool to spawn subagents; multiple Task calls in a single response = parallel spawning

### Workflow enforcement spectrum
- **Prompt-based** (instructions in system prompt) → non-zero failure rate
- **Programmatic** (hooks/gates that physically block tools) → 100% reliable
- Rule: use **programmatic enforcement** for financial, security, or compliance consequences

### Agent SDK hooks
- **PostToolUse hooks**: intercept tool results before the model processes them
- Use cases: normalizing heterogeneous data formats, blocking refunds above limits, compliance checks

### Task decomposition strategies
- **Fixed sequential pipelines**: predetermined steps; consistent but limited
- **Dynamic adaptive decomposition**: generates subtasks based on discoveries; flexible but less predictable
- **Attention dilution problem**: too many items in one pass → inconsistent depth — fix: local analysis passes + separate integration pass

### Session state and resumption
- `--resume` → continues a specific named session
- `fork_session` → creates an independent branch from a shared baseline
- Fresh start + summary injection → new session with an injected structured summary

---

## Domain 2: Claude Code Configuration & Workflows (20%)

### CLAUDE.md hierarchy (3 levels)
- `~/.claude/CLAUDE.md` — user-level; applies only to YOU; **NOT shared via git**
- `.claude/CLAUDE.md` or root `CLAUDE.md` — project-level; **version-controlled; applies to everyone**
- Directory-level `CLAUDE.md` — applies when working in that specific directory
- **Exam trap**: new team member not receiving instructions → instructions are at user-level instead of project-level
- Modular organization: use `@import` syntax; organize rules in `.claude/rules/` subdirectory

### Custom slash commands and skills
- `.claude/commands/` → project-scoped, shared
- `~/.claude/commands/` → personal
- `.claude/skills/` → on-demand with SKILL.md files
- Skill frontmatter: `context: fork` (isolated subagent execution), `allowed-tools` (restricts tools), `argument-hint` (prompts for required parameters)
- **Distinction**: Skills = on-demand, task-specific; CLAUDE.md = always-loaded, universal standards

### Path-specific rules
- Use YAML glob patterns (e.g., `paths: ["terraform/**/*"]`) to match files across the codebase
- More token-efficient than directory-level CLAUDE.md (rules load only when editing matching files)

### Plan Mode vs. Direct Execution
- Use **Plan Mode** for: complex multi-file changes, multiple valid approaches, architectural decisions, multi-phase investigations
- Use **Direct Execution** for: well-understood single-file changes

### CI/CD integration
- `-p` flag → runs Claude Code in non-interactive mode (prevents hanging CI jobs)
- `--output-format json` with `--json-schema` → machine-parseable findings
- Independent review instance catches more subtle issues than self-review
- Document testing standards in CLAUDE.md for CI-invoked instances

---

## Domain 3: Prompt Engineering & Structured Output (20%)

### Explicit criteria
- "Be conservative" and "high-confidence findings only" are **wrong**
- Correct: specific categorical criteria with code examples (e.g., "Flag comments only when claimed behavior contradicts actual code behavior")
- High false-positive rates in one category destroy trust in ALL categories

### Few-shot prompting
- Deploy when detailed instructions alone produce inconsistent results, or when the model makes inconsistent judgment calls on ambiguous cases
- Construct 2–4 targeted examples showing **reasoning** for why one action is chosen over alternatives

### Structured output via `tool_use`
- Using `tool_use` with JSON schemas eliminates syntax errors but **NOT** semantic errors, field placement errors, or fabrication
- Schema design: optional/nullable fields prevent fabrication; "unclear" enum for ambiguous cases; "other" + freeform field for extensibility

### Validation-retry loops
- Effective for: format mismatches, structural output errors
- Ineffective for: information genuinely absent from source
- Include original document + failed extraction + specific errors in follow-up requests
- Add `detected_pattern` fields to enable dismissal pattern analysis

### Batch API (Message Batches API)
- 50% cost savings
- Up to 24-hour processing window
- **No guaranteed latency SLA**
- **No multi-turn tool calling within a single request**
- Use `custom_id` for request/response correlation
- Rule: synchronous API for blocking workflows; Batch API for latency-tolerant overnight workflows

### Multi-instance review
- A model reviewing its own output retains reasoning context → less likely to question decisions
- Multi-pass architecture: local analysis passes (consistent depth) + separate integration pass (cross-file issues)

---

## Domain 4: Tool Design & MCP Integration (18%)

### Tool descriptions as the primary routing mechanism
- Descriptions drive LLM tool selection **more** than system prompts or function names
- A good description includes: primary purpose, input formats/constraints, example queries, edge cases/limitations, explicit boundaries vs. similar tools
- Misrouting fix hierarchy: (1) improve tool descriptions, (2) do NOT use few-shot examples (token overhead), (3) do NOT build routing classifiers (over-engineered)

### Structured error responses — 4 categories
- **Transient** (timeouts) → retryable
- **Validation** (invalid input) → fix input and retry
- **Business** (policy violations) → NOT retryable; needs alternative workflow
- **Permission** (access denied) → escalate or use different credentials
- Critical: access failure vs. valid empty result — confusing them breaks recovery logic

### Tool distribution and `tool_choice`
- Target **4–5 tools** per agent scoped to its role (18+ tools degrades reliability)
- `tool_choice` options:
  - `"auto"` → model decides (default)
  - `"any"` → model must call a tool, chooses which
  - `{"type": "tool", "name": "X"}` → forces a specific named tool
  - `{"type": "none"}` → no tools allowed

### MCP server integration
- **Project-level** `.mcp.json` → version-controlled and shared
- **User-level** `~/.claude.json` → personal, NOT shared
- Use environment variable expansion (`${GITHUB_TOKEN}`) to keep credentials out of version control
- Evaluate community MCP servers before building custom ones

### Built-in tools
- **Grep** → searches file contents for patterns
- **Glob** → matches file paths by naming patterns
- **Edit** → targeted modifications; fast
- **Read + Write** → fallback when Edit cannot find unique anchor text

---

## Domain 5: Context Management & Reliability (15%)

### Context preservation
- **Progressive summarization trap**: condensing history loses numerical values and specific details
- Fix: extract transactional facts into a persistent "case facts" block included in every prompt
- **"Lost in the middle" effect**: models reliably process beginning and end of long inputs but omit middle findings
- Mitigation: place summaries at top, use explicit section headers, trim verbose tool outputs

### Escalation patterns
- **Valid triggers**: customer explicitly requests human; policy exceptions or gaps; inability to make meaningful progress
- **Unreliable triggers**: sentiment-based escalation; self-reported confidence scores (models are confidently wrong on hard cases)
- Nuance: if issue is straightforward but customer is frustrated → offer resolution first; if customer explicitly requests a human → escalate immediately

### Error propagation in multi-agent systems
- Return structured error context: failure type, what was attempted, partial results, alternative approaches
- **Two anti-patterns**: silent suppression AND workflow termination
- Distinguish access failure (consider retry) from valid empty result (that IS the answer)

### Codebase exploration and context degradation
- Extended sessions → model references "typical patterns" instead of specific discoveries
- Mitigate with: scratchpad files, subagent delegation, summary injection, `/compact` command

### Human review and confidence calibration
- **Aggregate metrics trap**: 97% overall accuracy can hide 40% error rates on specific document types
- Use stratified random sampling by document type and field, not aggregate metrics
- Route low-confidence fields to human review

### Information provenance
- Each finding includes: claim + source URL + document name + excerpt + publication date
- On conflicting sources: annotate with BOTH values and source attribution; let the consumer decide
- Require publication/data collection dates in all outputs

---

## Five Core Mental Models (Tested Across All Domains)

1. **Programmatic enforcement vs. prompt-based guidance** — deterministic solution required for financial/security/compliance consequences
2. **Tool descriptions as the primary routing mechanism** — tool selection is driven by descriptions, not system prompts or function names
3. **Subagents do not inherit context** — every required piece of information must be explicitly passed
4. **"Lost in the middle" effect** — structure long-context inputs so critical information is at the beginning
5. **Batch API vs. real-time API** — this is a latency decision, not a universal cost optimization

---

## Prerequisites and Target Candidate

- **Target**: Solution architects with 6+ months hands-on experience building with Claude APIs, Agent SDK, Claude Code, and MCP in production
- **Formal prerequisite**: Completion of Anthropic Academy 200-level courses
- **Estimated prep time**:
  - Experienced daily Claude builders: 2–4 weeks (20–30 hours)
  - Experienced developers new to Claude: 6–10 weeks
  - New Claude developers: 2–4 months

---

## Registration and Cost

- **Cost**: Free for first 5,000 Claude Partner Network employees; **$99 per attempt** otherwise
- **Registration**:
  1. Apply to join the Claude Partner Network at `claude.com/partners`
  2. Request exam access via Anthropic Skilljar portal
  3. Complete prerequisite Anthropic Academy courses
  4. Schedule proctored exam via ProctorFree

---

## Study Resources

### Official (free)
- Anthropic Academy: `https://anthropic.skilljar.com/`
  - Claude 101
  - Building with the Claude API (8.1 hours)
  - Claude Code in Action
  - Introduction to Model Context Protocol (MCP)
  - Model Context Protocol: Advanced Topics
  - Introduction to agent skills
  - Introduction to subagents
- API docs: `https://docs.anthropic.com/en/docs/build-with-claude`
- Claude Code docs: `https://docs.anthropic.com/en/docs/claude-code`

### With exam access (via Skilljar)
- Official Exam Guide PDF — includes 12 sample questions with wrong-answer explanations
- Official 60-question practice test (target: score 900+/1000 before scheduling real exam)
- 4 hands-on building exercises

### Third-party free
- `claudecertifications.com` — free study guide, 25+ practice questions
- `certsafari.com/anthropic/claude-certified-architect` — 361 free practice questions
- `claudecertified.com/cca-practice-questions` — 105 practice questions (PDF)
- GitHub: `paullarionov/claude-certified-architect` — open-source study guide

---

## Common Exam Traps (Anti-Pattern Reference)

| Domain | Wrong answer | Right answer |
|--------|-------------|--------------|
| D1 | Loop terminates when Claude says "I'm done" | Loop terminates when `stop_reason == "end_turn"` |
| D1 | Use prompts to enforce financial rules | Use programmatic hooks/gates |
| D1 | Subagents auto-inherit coordinator context | Explicitly pass all needed data to subagents |
| D2 | Put shared instructions in `~/.claude/CLAUDE.md` | Put them in project-level `.claude/CLAUDE.md` |
| D2 | CI/CD runs Claude without `-p` flag | Always use `-p` for non-interactive CI |
| D3 | Instruct Claude to "be conservative" | Give specific categorical criteria with examples |
| D3 | Use Batch API for real-time responses | Use synchronous API for blocking workflows |
| D4 | Fix tool misrouting with few-shot examples | Fix tool misrouting by improving tool descriptions |
| D4 | Retry a business-rule violation error | Business errors are NOT retryable — use alternative workflow |
| D4 | Give Claude 18+ tools for complex tasks | Scope to 4–5 tools per agent |
| D5 | Progressively summarize conversation history | Extract transactional facts into persistent "case facts" block |
| D5 | Escalate when sentiment is negative | Escalate only when customer explicitly requests it or policy gap exists |
