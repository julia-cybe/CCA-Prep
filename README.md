# CCA-F Exam Prep

Hands-on study materials for the **Claude Certified Architect — Foundations (CCA-F)** certification by Anthropic.

## What this is

One Python exercise file per exam topic, each covering the key concepts and common exam traps for that area. The exercises are meant to be read, run, and reflected on — not just skimmed.

## Exam at a glance

| Attribute | Detail |
|-----------|--------|
| Questions | 60 multiple-choice, scenario-based |
| Time limit | 120 minutes |
| Passing score | 720 / 1,000 |
| Code writing | Not required — tests architecture decisions |

## Repo structure

```
.
├── certification-guide.md      # Full exam reference: domains, anti-patterns, traps
├── learning-plan.md            # Session-by-session study plan with reflection questions
├── domain1_agentic/            # Sessions 1–5: Agentic Architecture & Orchestration (27%)
├── domain2_claudecode/         # Sessions 9–11: Claude Code Configuration & Workflows (20%)
├── domain3_prompting/          # Sessions 12–14: Prompt Engineering & Structured Output (20%)
├── domain4_tools/              # Sessions 6–8: Tool Design & MCP Integration (18%)
└── domain5_context/            # Sessions 15–17: Context Management & Reliability (15%)
```

## Sessions

| # | Topic | Domain |
|---|-------|--------|
| 1 | Agentic loop | D1 |
| 2 | Tool choice & parallel calls | D1 |
| 3 | Multi-agent hub-and-spoke | D1 |
| 4 | Workflow enforcement: prompt vs. programmatic | D1 |
| 5 | Task decomposition & session state | D1 |
| 6 | Tool descriptions & routing | D4 |
| 7 | Structured error responses | D4 |
| 8 | MCP integration | D4 |
| 9 | CLAUDE.md hierarchy | D2 |
| 10 | Custom slash commands & skills | D2 |
| 11 | CI/CD integration | D2 |
| 12 | Explicit criteria & few-shot prompting | D3 |
| 13 | Structured output via tool_use | D3 |
| 14 | Batch API vs. synchronous API | D3 |
| 15 | Context preservation patterns | D5 |
| 16 | Escalation & human-in-the-loop | D5 |
| 17 | Error propagation in multi-agent systems | D5 |

## How to use

1. Read the session's exercise file — the docstring explains the key concepts
2. Uncomment `run_all()` and run it to see the concepts in action
3. Answer the reflection questions in `learnings.md` (gitignored — personal notes)
4. Check `certification-guide.md` for the exam anti-patterns relevant to that session

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install anthropic

export ANTHROPIC_API_KEY=your_key_here
```
