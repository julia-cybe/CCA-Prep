"""
Domain 5 Exercise 15: Context Preservation Patterns
CCA-F Topic: Context Management & Reliability

KEY CONCEPTS
============
1. Progressive summarization trap:
   — Each turn the history is summarized to save tokens
   — Summaries lose numbers, dates, specific amounts, exact policy wording
   — By turn 5+ the model works from an increasingly distorted picture
   — Dangerous in support, legal, financial contexts where precision matters

2. "Case facts" block:
   — A persistent structured dict (customer ID, incident date, amounts, etc.)
   — Injected verbatim into every prompt — never summarized, never inferred
   — Separates mutable conversation narrative from immutable factual anchors
   — Facts only update when the agent explicitly writes to the block

3. "Lost in the middle" effect:
   — Models reliably attend to the START and END of the context window
   — Material in the middle (especially pages 20–35 of a long doc) is under-attended
   — Fix: put critical facts at the TOP; close with a crisp summary of key points
   — Use explicit section headers so the model can re-anchor at each header
   — Trim verbose tool outputs — padding the middle buries important content

4. Trimming tool outputs:
   — Raw tool output (e.g., full DB row, full API response) pads the middle
   — Extract only the fields actually needed before injecting into context
   — Fewer tokens in the middle = less content competing for attention

EXERCISE STRUCTURE
==================
Version 1 — Progressive summarization: simulate 6-turn support conversation,
            summarize history each turn, observe what gets dropped
Version 2 — Case facts block: same conversation, facts live in a structured
            block injected fresh each turn, observe that numbers survive
Version 3 — Lost-in-the-middle demo: ask a question whose answer lives in the
            middle of a long document; observe retrieval failure vs. fix
"""

import anthropic
import json

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Scenario: customer support case with several precise facts that must survive
# ---------------------------------------------------------------------------

# These are the ground-truth facts. Version 1 will lose some; Version 2 won't.
GROUND_TRUTH = {
    "customer_id": "CUST-88421",
    "account_tier": "Pro",
    "incident_date": "2026-04-03",
    "failed_transactions": 3,
    "total_amount_disputed": 847.50,
    "policy_clause": "§4.2b",          # refund eligibility clause
    "refund_sla_days": 5,
    "agent_promised_callback": True,
    "callback_promised_by": "Agent Kim",
}

# The conversation unfolds over 6 turns. Each user message adds new plot detail
# but the KEY FACTS above must be retrievable at any turn.
CONVERSATION_TURNS = [
    # turn 1 — incident reported
    (
        "user",
        "Hi, I'm customer CUST-88421 on the Pro plan. On April 3rd I had 3 transactions "
        "fail in a row totalling $847.50. I need a refund under clause §4.2b.",
    ),
    # turn 2 — agent acknowledges, promises callback
    (
        "assistant",
        "I've logged your case. Under §4.2b you're eligible for a full refund of $847.50. "
        "Our SLA is 5 business days. Agent Kim will call you back within 24 hours.",
    ),
    # turn 3 — customer follows up, adds new info
    (
        "user",
        "It's been 2 days and Agent Kim still hasn't called. Also, I just noticed a fourth "
        "charge of $12.99 from the same date — can that be included too?",
    ),
    # turn 4 — agent responds
    (
        "assistant",
        "I'm sorry about the missed callback. I've escalated this. The $12.99 charge on "
        "April 3rd is under review — I'll confirm if it falls under the same clause.",
    ),
    # turn 5 — customer presses for specifics
    (
        "user",
        "What is the exact refund amount you have on file, and what clause covers it? "
        "I want to make sure nothing got lost.",
    ),
    # turn 6 — final summary request
    (
        "user",
        "Can you give me a full case summary: customer ID, original disputed amount, "
        "clause number, SLA, and who promised the callback?",
    ),
]

SYSTEM_PROMPT = "You are a customer support agent. Answer accurately based on the case history provided."


# ---------------------------------------------------------------------------
# SECTION 1: Progressive summarization
#
# After each assistant turn, the ENTIRE history is compressed into a summary.
# The next turn only sees the summary, not the original messages.
# Watch: numbers and clause references erode across turns.
# ---------------------------------------------------------------------------

def summarize_history(history_text: str) -> str:
    """Compress conversation history into a short summary (lossy)."""
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": (
                    "Summarize this customer support conversation in 3-4 sentences. "
                    "Be concise:\n\n" + history_text
                ),
            }
        ],
    )
    return response.content[0].text


def run_progressive_summarization() -> list[dict]:
    """
    Simulate 6-turn conversation with progressive summarization.
    Returns each turn's response + the running summary for inspection.
    """
    summary = ""   # starts empty; grows and compresses each turn
    results = []

    for i in range(0, len(CONVERSATION_TURNS), 2):
        user_msg = CONVERSATION_TURNS[i][1]
        expected_assistant = CONVERSATION_TURNS[i + 1][1] if i + 1 < len(CONVERSATION_TURNS) else None

        # Build context: summary so far + current user message
        context = f"Previous conversation summary:\n{summary}\n\n" if summary else ""
        prompt = context + f"Customer: {user_msg}"

        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        assistant_reply = response.content[0].text

        # Compress everything into a new summary (lossy step)
        history_so_far = (
            (f"Summary so far:\n{summary}\n\n" if summary else "")
            + f"Customer: {user_msg}\nAgent: {assistant_reply}"
        )
        summary = summarize_history(history_so_far)

        results.append(
            {
                "turn": i // 2 + 1,
                "user_msg": user_msg[:60] + "...",
                "assistant_reply": assistant_reply,
                "running_summary": summary,
            }
        )

    return results


# ---------------------------------------------------------------------------
# SECTION 2: Case facts block
#
# The structured facts dict is injected verbatim at the TOP of every prompt.
# Conversation narrative is still summarized (to save tokens) but facts never are.
# Numbers and clause references survive because they're never passed through
# a lossy summarization step.
# ---------------------------------------------------------------------------

def format_case_facts(facts: dict) -> str:
    """Render the case facts block as a clearly-labelled section."""
    lines = ["=== CASE FACTS (authoritative — do not infer or modify) ==="]
    for k, v in facts.items():
        lines.append(f"  {k}: {v}")
    lines.append("=== END CASE FACTS ===")
    return "\n".join(lines)


def run_case_facts_block() -> list[dict]:
    """
    Same 6-turn conversation. Facts injected fresh each turn.
    Conversation narrative may be summarized but facts are never at risk.
    """
    narrative_summary = ""
    results = []

    for i in range(0, len(CONVERSATION_TURNS), 2):
        user_msg = CONVERSATION_TURNS[i][1]

        # Inject facts block at the TOP, narrative summary below
        case_facts_section = format_case_facts(GROUND_TRUTH)
        context = case_facts_section + "\n\n"
        if narrative_summary:
            context += f"Conversation so far (summary):\n{narrative_summary}\n\n"
        prompt = context + f"Customer: {user_msg}"

        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        assistant_reply = response.content[0].text

        # Summarize only the narrative (facts live in the block, not here)
        narrative_so_far = (
            (f"Narrative summary so far:\n{narrative_summary}\n\n" if narrative_summary else "")
            + f"Customer: {user_msg}\nAgent: {assistant_reply}"
        )
        narrative_summary = summarize_history(narrative_so_far)

        results.append(
            {
                "turn": i // 2 + 1,
                "user_msg": user_msg[:60] + "...",
                "assistant_reply": assistant_reply,
            }
        )

    return results


# ---------------------------------------------------------------------------
# SECTION 3: "Lost in the middle" demo
#
# Create a long document where the answer to the question sits in the middle.
# Version A: question placed at the end (answer in middle → likely missed).
# Version B: critical fact moved to the top + question at the end (reliably found).
# ---------------------------------------------------------------------------

def make_long_document() -> str:
    """Build a ~2000-token document where the key fact is buried in the middle."""
    filler = (
        "This section covers general account management policies. "
        "Customers should ensure their contact details are up to date. "
        "Billing cycles run on the first of each month. "
        "Tier upgrades take effect immediately upon payment. "
    ) * 10  # repeated to push the middle content away from edges

    key_fact = (
        "\n\n--- REFUND POLICY (§4.2b) ---\n"
        "Pro-tier customers who experience 3 or more failed transactions "
        "within a single calendar day are eligible for a full refund of all "
        "affected charges. Refund requests must be submitted within 14 days. "
        "Processing time: 5 business days. Contact refunds@example.com.\n"
        "--- END REFUND POLICY ---\n\n"
    )

    more_filler = (
        "Support hours are Monday through Friday, 9am–6pm local time. "
        "For urgent issues outside business hours, use the emergency hotline. "
        "Escalation requests are reviewed by a senior agent within 2 hours. "
        "Customer satisfaction surveys are sent after every resolved ticket. "
    ) * 10

    # Key fact in the MIDDLE — flanked by filler on both sides
    return filler + key_fact + more_filler


def ask_about_refund_policy(document: str, critical_fact_at_top: bool) -> str:
    """
    Ask about the refund policy SLA.
    With critical_fact_at_top=False: answer is buried in the middle (lost-in-middle risk).
    With critical_fact_at_top=True: critical section is duplicated at the top as well.
    """
    if critical_fact_at_top:
        # Mitigation: put the key section at the TOP before the full document
        preamble = (
            "IMPORTANT — KEY POLICY EXCERPT (full document follows):\n"
            "§4.2b refund SLA is 5 business days for Pro-tier customers "
            "with 3+ failed transactions in one day.\n\n"
        )
        content = preamble + "Full policy document:\n\n" + document
    else:
        content = "Policy document:\n\n" + document

    content += "\n\nQuestion: What is the refund processing SLA for a Pro-tier customer under §4.2b?"

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=128,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text


# ---------------------------------------------------------------------------
# SECTION 4: Run all sections and print observations
# ---------------------------------------------------------------------------

def run_all():
    print("=" * 70)
    print("CONTEXT PRESERVATION: Summarization vs. Facts Block vs. Lost-in-Middle")
    print("=" * 70)

    # --- Section 1: Progressive summarization ---
    print("\n[1] Progressive summarization — watch for fact erosion")
    v1_results = run_progressive_summarization()
    final_turn = v1_results[-1]
    print(f"\nFinal turn response (turn {final_turn['turn']}):")
    print(f"  {final_turn['assistant_reply']}")
    print(f"\nRunning summary after final turn:")
    print(f"  {final_turn['running_summary']}")
    print("\n  Check: does the summary still mention CUST-88421, $847.50, §4.2b, Agent Kim?")

    # --- Section 2: Case facts block ---
    print("\n[2] Case facts block — same conversation, facts injected fresh each turn")
    v2_results = run_case_facts_block()
    final_turn_v2 = v2_results[-1]
    print(f"\nFinal turn response (turn {final_turn_v2['turn']}):")
    print(f"  {final_turn_v2['assistant_reply']}")
    print("\n  Check: does the response correctly cite CUST-88421, $847.50, §4.2b, Agent Kim?")

    # --- Section 3: Lost in the middle ---
    print("\n[3] Lost in the middle")
    doc = make_long_document()
    print(f"  Document length: {len(doc.split())} words (key fact in middle)")

    answer_without_fix = ask_about_refund_policy(doc, critical_fact_at_top=False)
    answer_with_fix = ask_about_refund_policy(doc, critical_fact_at_top=True)

    print(f"\n  Without fix (answer buried in middle):\n    {answer_without_fix}")
    print(f"\n  With fix (key fact duplicated at top):\n    {answer_with_fix}")
    print("\n  Expected: '5 business days'. Does the unfixed version get it right?")

    print("\n" + "=" * 70)
    print("WHAT TO OBSERVE")
    print("=" * 70)
    print("""
Version 1 — Progressive summarization:
  Numbers erode first: "$847.50" becomes "a disputed amount" or disappears
  Clause references drop: "§4.2b" becomes "the refund policy"
  Named agents drop: "Agent Kim" becomes "an agent"
  By turn 5–6 the model is working from a paraphrase, not ground truth
  Risk: model confidently states wrong amounts or cites the wrong clause

Version 2 — Case facts block:
  Every turn starts with the authoritative block at the TOP of the prompt
  The model reads exact values directly — no inference, no paraphrase
  Narrative summary can still be lossy; it only carries conversational flow
  Key insight: separate WHAT HAS HAPPENED (summarizable) from
               WHAT IS TRUE (must never be paraphrased)

Version 3 — Lost in the middle:
  Models attend strongly to start and end of context; middle gets less attention
  A 3-paragraph policy buried between 20+ paragraphs of filler may be missed
  Fix 1: move critical content to the top
  Fix 2: close with a crisp summary of key points
  Fix 3: use explicit section headers — model can re-anchor at each header
  Fix 4: trim verbose tool outputs that pad the middle unnecessarily

/compact in Claude Code:
  Summarizes the conversation history mid-session to free context window space
  Same tradeoff applies: facts and exact values in the middle of the history
  may be lost in the compact summary — use case facts / structured memory
  to preserve anything that must survive a /compact
""")


# ---------------------------------------------------------------------------
# REFLECTION QUESTIONS (answer in learnings.md)
# ---------------------------------------------------------------------------

REFLECTION = """
REFLECTION QUESTIONS — answer in learnings.md
==============================================

1. Why does progressive summarization fail for numerical values specifically?

2. What goes in a "case facts" block vs. what stays in the message history?

3. A model analyzes a 50-page document and misses key findings in pages 20–35.
   What effect is this, and how do you fix it?

4. How does trimming verbose tool outputs help with the "lost in the middle" effect?

5. What is the /compact command in Claude Code and when does it help?
"""


if __name__ == "__main__":
    # Uncomment to run the live demo (uses API credits):
    # run_all()

    print(REFLECTION)
    print(
        "\nKey patterns:\n"
        "  Progressive summarization → numbers/clauses/names erode across turns\n"
        "  Case facts block          → inject structured facts fresh at TOP every turn\n"
        "  Lost in the middle        → critical info at top + headers + trim filler"
    )
