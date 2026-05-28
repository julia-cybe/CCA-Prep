# CCA-F Learning Plan

Sessions 1–2 already done (agentic loop + tool choice/parallel calls).
Each session = one exercise file + reflection questions answered in learnings.md.
Sessions roughly mirror exam domain weighting: Domain 1 (27%) gets the most sessions.

---

## Domain 1: Agentic Architecture & Orchestration (27%) — Sessions 1–5

### Session 1  — The Agentic Loop
**File**: `domain1_agentic/ex01_agentic_loop.py`
**Covers**:
- `stop_reason`: `tool_use` vs `end_turn` vs `max_tokens` vs `stop_sequence`
- Message flow: how tool_use blocks and tool_result blocks are appended
- Why tool results are `role="user"`, not `role="assistant"`
- Stateful (in-context) vs stateless (cross-session) state

**Key takeaway**: The loop is the foundation of every agentic system. `stop_reason` is the only reliable termination signal.

---

### Session 2  — Tool Choice & Parallel Tool Calls
**File**: `domain1_agentic/ex02_tool_choice_parallel.py`
**Covers**:
- `tool_choice`: `"auto"`, `{"type": "any"}`, `{"type": "tool", "name": "X"}`, `{"type": "none"}`
- Parallel tool calls: Claude calling multiple tools in ONE turn (single API round-trip)
- Why parallel calls matter: latency reduction in production agents
- All tool_result blocks for a parallel turn go in a single user message

**Key takeaway**: You control Claude's tool usage. Parallel calls = fewer round-trips = faster agents.

---

### Session 3  — Multi-Agent Hub-and-Spoke Orchestration
**File**: `domain1_agentic/ex03_multi_agent.py`
**Covers**:
- Coordinator / subagent architecture (hub-and-spoke)
- Subagents do NOT inherit coordinator's conversation history
- How to explicitly pass context into a subagent's prompt
- Spawning multiple subagents in parallel (multiple Task calls in one response)
- Result aggregation back to the coordinator

**Exercise**: Build a coordinator that receives "Research AAPL and GOOG stocks" and spawns two subagents — one per ticker — each getting only the context they need. Coordinator aggregates results.

**Reflection questions**:
1. What happens if you forget to pass the task description to a subagent?
2. If both subagents can run in parallel, how do you spawn them simultaneously?
3. What is the coordinator responsible for that subagents are NOT?
4. How is this different from just calling two tools in one turn (Session 2)?
5. When would you choose subagents over parallel tool calls?

---

### Session 4  — Workflow Enforcement: Prompt vs. Programmatic
**File**: `domain1_agentic/ex04_enforcement.py`
**Covers**:
- Prompt-based enforcement: instructions in system prompt (non-zero failure rate)
- Programmatic enforcement: interceptors/hooks that block tool execution (100% reliable)
- PostToolUse hooks: intercept tool results before the model processes them
- When programmatic enforcement is REQUIRED: financial, security, compliance consequences

**Exercise**: Build an agent that processes refund requests. First version: prompt-only guardrail ("never approve refunds over $500"). Second version: programmatic gate that intercepts tool results and blocks the approve_refund call if amount > $500, regardless of what Claude decides.

**Reflection questions**:
1. With prompt-only enforcement, what scenario causes it to fail?
2. What is a PostToolUse hook and where in the agentic loop does it fire?
3. Give 3 real-world examples where programmatic enforcement is required vs. where a prompt is sufficient.
4. What is the difference between blocking at the tool call level vs. overriding the tool result?
5. How does this relate to the exam's "workflow enforcement spectrum"?

---

### Session 5  — Task Decomposition & Session State
**File**: `domain1_agentic/ex05_decomposition_state.py`
**Covers**:
- Fixed sequential pipelines vs. dynamic adaptive decomposition
- Attention dilution problem: analyzing too many items in one pass
- Local analysis passes + separate integration pass pattern
- Session resumption: `--resume`, `fork_session`, fresh start + summary injection
- In-context state (messages list) vs. external state (database/file)

**Exercise**: Build an agent that analyzes 10 code files. Version 1: sends all 10 in one prompt (observe attention dilution). Version 2: sends files one at a time (local analysis passes), then synthesizes findings in a final integration call.

**Reflection questions**:
1. What is the attention dilution problem and how does the two-pass approach solve it?
2. When would you use `fork_session` instead of `--resume`?
3. What information should go in a "summary injection" when starting a fresh session?
4. What is the difference between fixed sequential and dynamic adaptive decomposition — when does each shine?
5. Where does session state live in the ex01 agentic loop, and what would you need to add to persist it across sessions?

---

## Domain 4: Tool Design & MCP Integration (18%) — Sessions 6–8

### Session 6  — Tool Descriptions & Routing
**File**: `domain4_tools/ex06_tool_descriptions.py`
**Covers**:
- Tool descriptions as the **primary** routing mechanism (more important than system prompts or function names)
- What makes a good description: purpose, input formats, constraints, example queries, edge cases, explicit boundaries vs. similar tools
- Misrouting fix hierarchy: (1) improve description → (2) NOT few-shot examples → (3) NOT routing classifiers
- 4–5 tools per agent is the reliable range; 18+ degrades reliability

**Exercise**: Create 3 tools with intentionally bad descriptions — watch Claude misroute. Fix descriptions one at a time and observe routing improve. Then test what happens with 10 tools in one agent.

**Reflection questions**:
1. You have tools `search_documents` and `search_web`. Claude keeps calling the wrong one. What is the fix?
2. Why is adding few-shot examples NOT the right way to fix misrouting?
3. What specific information in a tool description most reliably steers routing?
4. At what tool count does reliability start to degrade, and why?
5. A PM suggests building a routing classifier in front of the tools. What's wrong with this?

---

### Session 7 — Structured Error Responses
**File**: `domain4_tools/ex07_error_handling.py`
**Covers**:
- 4 error categories: transient (retryable), validation (fix + retry), business (NOT retryable), permission (escalate)
- Access failure vs. valid empty result — this distinction breaks recovery logic when confused
- Structured error context: failure type, what was attempted, partial results, alternative approaches
- Two anti-patterns: silent error suppression AND hard workflow termination

**Exercise**: Build a tool that can return all 4 error types. Build a recovery loop that correctly handles each: retries transient errors with backoff, asks Claude to fix input for validation errors, routes to alternative workflow for business errors, escalates for permission errors.

**Reflection questions**:
1. A refund API returns 403 because the user's account lacks permissions. What error category is this? Retryable?
2. A search tool returns an empty list because no results matched. Is this an error? How should it be structured?
3. What is the difference between "silent suppression" and a useful error response?
4. An agent retries a business-rule violation 3 times. What's wrong with this approach?
5. What fields should a structured error response always include?

---

### Session 8  — MCP Integration
**File**: `domain4_tools/ex08_mcp_integration.py`
**Covers**:
- MCP server: what it is and how it exposes tools to Claude
- Project-level `.mcp.json` (version-controlled, shared) vs. user-level `~/.claude.json` (personal, not shared)
- Credential management: `${ENV_VAR}` expansion to keep secrets out of version control
- When to use community MCP servers vs. building custom ones
- `resources` vs. `tools` in MCP

**Exercise**: Configure a local MCP server (e.g., filesystem or fetch). Write a `.mcp.json` for project scope and a separate user-level config. Observe which config Claude Code picks up and why.

**Reflection questions**:
1. A teammate opens the project and doesn't see your MCP server. Where did you put the config?
2. Why should you never hardcode API keys directly in `.mcp.json`?
3. What is the difference between an MCP `tool` and an MCP `resource`?
4. When is building a custom MCP server worth it vs. using an existing community one?
5. What is the scope difference between project-level and user-level MCP configs?

---

## Domain 2: Claude Code Configuration & Workflows (20%) — Sessions 9–11

### Session 9 — CLAUDE.md Hierarchy
**File**: `domain2_claudecode/ex09_claude_md.md` (a conceptual exercise — no Python)
**Covers**:
- 3-level hierarchy: user-level, project-level, directory-level
- Which level is version-controlled and shared vs. personal
- `@import` syntax for modular rules
- Path-specific rules with YAML glob patterns (more token-efficient than directory CLAUDE.md)
- Exam trap: new team member not receiving instructions

**Exercise**: Create a mock project with all 3 CLAUDE.md levels. Intentionally put a rule at user-level that should be at project-level. Observe that a "new team member" (fresh clone, no user-level config) doesn't see it. Fix by moving to project-level.

**Reflection questions**:
1. Your team has a rule "always write tests in pytest." Where should it live and why?
2. A rule "my name is Julia, always address me by name" — where does this belong?
3. You have 50 lines of Terraform rules that only apply to `.tf` files. What's more efficient: directory-level CLAUDE.md or path-specific rules?
4. What does `@import` let you do, and where are the imported files typically stored?
5. A new developer joins and says Claude ignores all the team standards. What's the most likely cause?

---

### Session 10 — Custom Slash Commands & Skills
**File**: `domain2_claudecode/ex10_skills_commands.md` (conceptual + hands-on config)
**Covers**:
- Custom slash commands: `.claude/commands/` (project) vs. `~/.claude/commands/` (personal)
- Skills vs. CLAUDE.md: on-demand task-specific vs. always-loaded universal standards
- Skill frontmatter: `context: fork`, `allowed-tools`, `argument-hint`
- `context: fork` → skill runs as an isolated subagent, protecting main context
- When to build a skill vs. writing a slash command vs. putting rules in CLAUDE.md

**Exercise**: Create a project-level slash command `/review-pr`. Create a skill `security-audit` with `context: fork` and `allowed-tools: [Grep, Read]`. Observe how fork isolation prevents the skill from polluting the main conversation context.

**Reflection questions**:
1. What is the difference between a custom slash command and a skill?
2. Why would you set `context: fork` on a skill?
3. A skill needs the PR number as input. Which frontmatter field do you use?
4. Should "always use 4-space indentation" live in a skill or CLAUDE.md? Why?
5. A teammate has a personal slash command `/standup` they want to share with the team. Where should it be moved?

---

### Session 11 — CI/CD Integration with Claude Code
**File**: `domain2_claudecode/ex11_cicd.sh` (bash + yaml config)
**Covers**:
- `-p` flag: non-interactive mode (prevents CI pipeline from hanging waiting for input)
- `--output-format json` + `--json-schema`: machine-parseable findings for CI
- Independent review instance vs. self-review
- Plan Mode: when to use it vs. direct execution
- Documenting testing standards in CLAUDE.md for CI-invoked instances

**Exercise**: Write a GitHub Actions workflow that uses Claude Code to review a PR. Version 1: without `-p` — observe hang. Version 2: with `-p` and JSON output — observe clean exit and parseable results.

**Reflection questions**:
1. What does the `-p` flag do and what breaks without it in CI?
2. Why does an independent Claude review instance catch more subtle issues than self-review?
3. What output format should a CI Claude invocation use for downstream parsing?
4. In what type of situation should you engage Plan Mode instead of letting Claude execute directly?
5. Why put testing standards in CLAUDE.md instead of in the CI pipeline YAML?

---

## Domain 3: Prompt Engineering & Structured Output (20%) — Sessions 12–14

### Session 12 — Explicit Criteria & Few-Shot Prompting
**File**: `domain3_prompting/ex12_criteria_fewshot.py`
**Covers**:
- "Be conservative" is wrong — specific categorical criteria with code examples is right
- High false-positive rates in one category destroy trust in ALL categories
- When to deploy few-shot: after detailed instructions still produce inconsistent results
- 2–4 examples, each showing the reasoning process (not just the answer)
- Examples must show WHY one action is chosen over alternatives

**Exercise**: Build a code review agent. Version 1: prompt says "be conservative, only flag high-confidence issues." Observe inconsistent flagging. Version 2: explicit categorical criteria ("flag ONLY when X"). Version 3: add 3 few-shot examples showing reasoning. Compare false-positive rates across all 3.

**Reflection questions**:
1. Why is "only flag high-confidence issues" a bad instruction?
2. What makes a few-shot example useful vs. just padding? What must it demonstrate?
3. When should you NOT use few-shot examples for tool routing?
4. A model has a 15% false-positive rate on one category but 2% overall. Why does the 15% matter?
5. Write a specific categorical criterion for "flag a comment as misleading." What does it include?

---

### Session 13 — Structured Output via tool_use & JSON Schemas
**File**: `domain3_prompting/ex13_structured_output.py`
**Covers**:
- Using `tool_use` to enforce structured output (not just for calling tools)
- What JSON schemas prevent (syntax errors) vs. what they DON'T prevent (semantic errors, fabrication)
- Schema design: optional/nullable fields, "unclear" enum, "other" + freeform for extensibility
- Validation-retry loops: when they work and when they don't
- Include original doc + failed extraction + specific errors in retry request

**Exercise**: Build a document extraction agent using `tool_use` with a strict JSON schema. Test: what happens when the schema field is required but information is absent from the document (fabrication risk). Fix with optional/nullable fields and "unclear" enum value.

**Reflection questions**:
1. Why use `tool_use` for structured output when there's no tool to call?
2. A JSON schema marks `customer_name` as required. The document doesn't mention the customer. What does Claude do?
3. What is the difference between a syntax error and a semantic error in structured output?
4. A validation-retry loop keeps failing on the same field. What does this tell you?
5. When is a validation-retry loop the wrong solution?

---

### Session 14 — Batch API vs. Synchronous API
**File**: `domain3_prompting/ex14_batch_api.py`
**Covers**:
- Message Batches API: 50% cost savings, up to 24-hour window, no latency SLA
- NO multi-turn tool calling within a single batch request
- `custom_id` for request/response correlation
- Decision rule: synchronous for blocking/real-time; batch for latency-tolerant overnight
- Multi-instance review: why self-review is less reliable

**Exercise**: Build a batch job that processes 20 documents overnight. Assign each a `custom_id`. Process results when complete, correlating back to source documents. Compare cost and turnaround vs. sequential synchronous calls.

**Reflection questions**:
1. A user submits a support ticket and expects a response within 30 seconds. Synchronous or Batch API?
2. You need to analyze 10,000 contracts overnight for legal review. Synchronous or Batch?
3. Why can't you do multi-turn tool calling in a single batch request?
4. What is `custom_id` and why is it important in batch workflows?
5. Why does a model reviewing its own output produce fewer corrections than an independent review instance?

---

## Domain 5: Context Management & Reliability (15%) — Sessions 15–17

### Session 15 — Context Preservation Patterns
**File**: `domain5_context/ex15_context_preservation.py`
**Covers**:
- Progressive summarization trap: summarizing loses numbers and specific facts
- "Case facts" block: persistent structured facts included in every prompt
- "Lost in the middle" effect: models process start and end reliably; middle gets omitted
- Mitigation: put critical info at top, use explicit section headers, trim verbose tool outputs

**Exercise**: Simulate a long customer support conversation. Version 1: progressively summarize. Observe what gets dropped (numbers, specific policy violations). Version 2: maintain a persistent "case facts" block with structured data (customer ID, incident date, amounts). Observe that facts survive across many turns.

**Reflection questions**:
1. Why does progressive summarization fail for numerical values specifically?
2. What goes in a "case facts" block vs. what stays in the message history?
3. A model analyzes a 50-page document and misses key findings in pages 20–35. What effect is this, and how do you fix it?
4. How does trimming verbose tool outputs help with the "lost in the middle" effect?
5. What is the `/compact` command in Claude Code and when does it help?

---

### Session 16 — Escalation Patterns & Human-in-the-Loop
**File**: `domain5_context/ex16_escalation.py`
**Covers**:
- Valid escalation triggers: explicit human request, policy gaps, inability to make progress
- Invalid triggers: sentiment detection, self-reported confidence scores
- Sentiment nuance: frustrated customer + straightforward issue → offer resolution first
- Confidence nuance: models are confidently wrong on hard cases — self-reported confidence is unreliable
- Aggregate metrics trap: 97% overall can hide 40% error rate on one document type
- Stratified sampling by document type, not aggregate accuracy

**Exercise**: Build a customer support agent with an escalation function. Test 3 cases: (a) frustrated customer but easy issue — should NOT escalate first, (b) customer explicitly says "I want to speak to a human" — must escalate immediately, (c) agent can't find a policy to cover the case — must escalate. Add a confidence score and observe it's unreliable.

**Reflection questions**:
1. A customer says "I'm extremely frustrated with this service." Should the agent escalate? Why or why not?
2. A customer says "Just give me a human." What does the agent do next?
3. Why are self-reported confidence scores unreliable as escalation triggers?
4. Your extraction pipeline reports 97% accuracy. Why might this be misleading?
5. What is stratified sampling and why is it better than aggregate accuracy metrics?

---

### Session 17 — Error Propagation in Multi-Agent Systems
**File**: `domain5_context/ex17_error_propagation.py`
**Covers**:
- Structured error context: failure type + what was attempted + partial results + alternative approaches
- Silent suppression anti-pattern: agent succeeds but hides a failed subagent
- Hard termination anti-pattern: entire workflow fails because one subagent failed
- Access failure vs. valid empty result
- Graceful degradation: return partial results with clear attribution

**Exercise**: Build a research coordinator with 3 subagents. One subagent fails (simulated). Version 1: silent suppression (coordinator pretends everything succeeded). Version 2: hard termination (entire workflow aborts). Version 3: structured error propagation (coordinator returns partial results with a clear note on which subagent failed and why, plus suggested alternatives).

**Reflection questions**:
1. What 4 pieces of information should a structured error response always include?
2. A database subagent returns an empty list because no records matched the query. Is this an error?
3. How is "silent suppression" harmful in a multi-agent system?
4. How is "hard termination on any subagent failure" harmful?
5. What is the difference between "access failure" and "valid empty result" and why does confusing them break recovery logic?

---

## Final Prep — Session 18: Practice Exam Simulation
**File**: `final_prep/ex18_practice_exam.md`
**Covers**:
- Work through all exam anti-patterns from `certification-guide.md`
- Run through all 5 domains, identify weak areas
- Use `certsafari.com` 361-question bank: score by domain
- Use official 60-question practice test via Skilljar: target 900+/1000 before scheduling

**Checklist before scheduling the real exam**:
- [ ] Score 900+/1000 on official practice test
- [ ] Can explain all 5 core mental models from memory
- [ ] Can recite the 4 error categories and correct response to each
- [ ] Know CLAUDE.md hierarchy cold (3 levels, which is shared, which is personal)
- [ ] Know `tool_choice` options and when to use each
- [ ] Know Batch API limitations cold (no multi-turn tool use, no latency SLA)
- [ ] Know the exact exam trap for each domain (see certification-guide.md anti-pattern table)

---

## Quick Reference: Session → Domain Mapping

| Session | Topic | Exam Domain | Weight |
|---------|-------|-------------|--------|
| 1 | Agentic loop | D1 | 27% |
| 2 | Tool choice & parallel calls | D1 | 27% |
| 3 | Multi-agent hub-and-spoke | D1 | 27% |
| 4 | Enforcement: prompt vs. programmatic | D1 | 27% |
| 5 | Task decomposition & session state | D1 | 27% |
| 6 | Tool descriptions & routing | D4 | 18% |
| 7 | Structured error responses | D4 | 18% |
| 8 | MCP integration | D4 | 18% |
| 9 | CLAUDE.md hierarchy | D2 | 20% |
| 10 | Custom slash commands & skills | D2 | 20% |
| 11 | CI/CD integration | D2 | 20% |
| 12 | Explicit criteria & few-shot | D3 | 20% |
| 13 | Structured output via tool_use | D3 | 20% |
| 14 | Batch API vs. synchronous API | D3 | 20% |
| 15 | Context preservation patterns | D5 | 15% |
| 16 | Escalation & human-in-the-loop | D5 | 15% |
| 17 | Error propagation in multi-agent | D5 | 15% |
| 18 | Practice exam simulation | All | — |
