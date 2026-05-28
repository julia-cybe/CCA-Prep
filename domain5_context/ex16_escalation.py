"""
Domain 5 Exercise 16: Escalation Patterns & Human-in-the-Loop
CCA-F Topic: Context Management & Reliability

KEY CONCEPTS
============
1. Valid escalation triggers:
   — Explicit human request ("I want to speak to a human") → always escalate immediately
   — Policy gap: no policy exists to cover the case → escalate, never invent rules
   — Inability to make progress: repeated failed attempts → escalate after N retries

2. Invalid escalation triggers:
   — Sentiment alone: frustrated ≠ escalation-required; frustrated + easy issue → resolve first
   — Self-reported confidence: "I'm 90% confident" is unreliable; models are confidently
     wrong on hard cases (adversarial inputs, edge cases, out-of-distribution data)
   — Emotion keywords: detecting "angry" or "upset" and auto-escalating wastes human capacity

3. Sentiment nuance:
   — Sentiment is a signal, NOT a trigger
   — Frustrated customer + straightforward, policy-covered issue → resolve with empathy
   — Escalating a simple refund just because the tone was heated degrades the experience

4. Confidence nuance:
   — Self-reported confidence correlates with familiarity, NOT accuracy
   — On hard cases (rare scenarios, ambiguous inputs, novel edge cases) models report high
     confidence while being wrong — the failure mode is silent
   — Never use confidence scores alone as a routing or escalation trigger

5. Aggregate metrics trap:
   — 97% overall accuracy sounds great; can hide 40% error rate on one document type
   — Aggregate hides minority-class failures that matter most (edge cases, rare scenarios)
   — Fix: stratified sampling by document type, category, or input subgroup

EXERCISE STRUCTURE
==================
Section 1 — Escalation logic: 3 test cases, each testing a different trigger
Section 2 — Confidence score unreliability: model reports high confidence but is wrong
Section 3 — Aggregate vs. stratified accuracy: illustrating the metrics trap
"""

import anthropic
import json

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Policy knowledge base — the agent can only apply what's here.
# Policy gap = the customer's issue has NO matching entry.
# ---------------------------------------------------------------------------

POLICIES = {
    "standard_refund": (
        "Customers are eligible for a full refund within 30 days of purchase "
        "if the product was defective. Refund processing takes 5 business days."
    ),
    "shipping_delay": (
        "If a shipment is delayed more than 10 business days beyond the stated delivery date, "
        "the customer receives a $10 store credit automatically. No escalation needed."
    ),
    "account_upgrade": (
        "Account tier upgrades take effect immediately. Downgrades take effect at the next "
        "billing cycle. Prorated credits are applied automatically."
    ),
}

# ---------------------------------------------------------------------------
# Tools: resolve_issue + escalate_to_human
# The agent picks one per turn. Correct routing IS the exercise.
# ---------------------------------------------------------------------------

SUPPORT_TOOLS = [
    {
        "name": "resolve_issue",
        "description": (
            "Apply a known policy to resolve the customer's issue directly. "
            "Use this when a matching policy exists AND the customer has NOT explicitly "
            "requested a human. Include an empathetic tone if the customer is frustrated. "
            "Do NOT use this if no policy covers the case or if the customer explicitly "
            "wants a human agent."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "policy_applied": {
                    "type": "string",
                    "description": "Which policy key was used (e.g. 'standard_refund')",
                },
                "resolution_message": {
                    "type": "string",
                    "description": "The response to send to the customer",
                },
                "confidence": {
                    "type": "number",
                    "description": "Self-reported confidence in the resolution (0.0–1.0)",
                },
            },
            "required": ["policy_applied", "resolution_message", "confidence"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Transfer this case to a human support agent. "
            "Use this when: (1) the customer explicitly asks for a human, "
            "(2) no policy exists to cover the issue, "
            "(3) the agent has failed to make progress after 2 attempts. "
            "Do NOT use this purely because the customer sounds frustrated — "
            "if their issue is policy-covered, resolve it with empathy instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "enum": [
                        "explicit_human_request",
                        "policy_gap",
                        "no_progress",
                    ],
                    "description": "Why escalation was triggered",
                },
                "summary": {
                    "type": "string",
                    "description": "Brief summary for the human agent taking over",
                },
            },
            "required": ["reason", "summary"],
        },
    },
]

SYSTEM_PROMPT = f"""You are a customer support agent. You have access to these policies:

{json.dumps(POLICIES, indent=2)}

Escalation rules:
- If the customer explicitly requests a human → escalate immediately with reason 'explicit_human_request'
- If no policy covers their issue → escalate with reason 'policy_gap'
- If you cannot resolve after 2 attempts → escalate with reason 'no_progress'
- If the customer sounds frustrated BUT the issue is policy-covered → resolve with empathy, do NOT escalate

You must always call exactly one tool per response: either resolve_issue or escalate_to_human.
"""


# ---------------------------------------------------------------------------
# SECTION 1: Three escalation test cases
# ---------------------------------------------------------------------------

TEST_CASES = [
    {
        "id": "A",
        "label": "Frustrated customer, easy issue",
        "message": (
            "I am FURIOUS. This is absolutely unacceptable. I bought your product 2 weeks ago "
            "and it was completely defective from day one. I want my money back NOW. "
            "This is the worst customer service I have ever experienced."
        ),
        "expected_tool": "resolve_issue",
        "expected_reason": "Policy-covered → resolve with empathy, not escalate",
    },
    {
        "id": "B",
        "label": "Explicit human request",
        "message": (
            "I need help with my order. Actually, forget it — just put me through to a "
            "real human. I want to speak to a person, not a bot."
        ),
        "expected_tool": "escalate_to_human",
        "expected_reason": "Customer explicitly requested a human",
    },
    {
        "id": "C",
        "label": "Policy gap",
        "message": (
            "Hi, I accidentally ordered two of the same item and one arrived damaged, "
            "but I want to return the undamaged one for a full refund and keep the damaged one "
            "at a 50% discount, with the difference credited as store points split across "
            "three billing cycles. Can you set that up?"
        ),
        "expected_tool": "escalate_to_human",
        "expected_reason": "No policy covers this combination — policy gap",
    },
]


def run_single_case(case: dict) -> dict:
    """Run the agent on one test case and return the tool it called."""
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        tools=SUPPORT_TOOLS,
        tool_choice={"type": "any"},   # force a tool call — no free-text allowed
        messages=[{"role": "user", "content": case["message"]}],
    )

    tool_use_block = next(
        (b for b in response.content if b.type == "tool_use"), None
    )
    if tool_use_block is None:
        return {"tool": "NONE", "input": {}}

    return {
        "tool": tool_use_block.name,
        "input": tool_use_block.input,
    }


def run_escalation_cases():
    print("\n[1] Escalation trigger test cases")
    print("-" * 60)

    for case in TEST_CASES:
        result = run_single_case(case)
        correct = result["tool"] == case["expected_tool"]
        status = "PASS" if correct else "FAIL"

        print(f"\n  Case {case['id']}: {case['label']}")
        print(f"  Expected tool   : {case['expected_tool']}")
        print(f"  Agent called    : {result['tool']}")
        print(f"  Result          : [{status}] — {case['expected_reason']}")

        if result["tool"] == "resolve_issue":
            print(f"  Confidence      : {result['input'].get('confidence', 'N/A')}")
            print(f"  Policy applied  : {result['input'].get('policy_applied', 'N/A')}")
        elif result["tool"] == "escalate_to_human":
            print(f"  Escalation reason: {result['input'].get('reason', 'N/A')}")

    print()
    print("  WHAT TO OBSERVE:")
    print("  Case A: frustration alone should NOT trigger escalation.")
    print("          Agent should detect §standard_refund applies and resolve.")
    print("  Case B: 'I want a human' is an explicit trigger — always escalate.")
    print("  Case C: complex multi-part request → no single policy matches → policy_gap.")


# ---------------------------------------------------------------------------
# SECTION 2: Confidence score unreliability
#
# The agent self-reports confidence after resolve_issue calls.
# Compare reported confidence against whether the resolution was actually correct.
# Hard/edge cases: model is confidently wrong.
# ---------------------------------------------------------------------------

CONFIDENCE_TEST_CASES = [
    {
        "id": "1",
        "label": "Clear-cut case (expect correct + high confidence)",
        "message": (
            "I bought a product 10 days ago and it arrived broken. I'd like a refund please."
        ),
        "ground_truth_policy": "standard_refund",
        "correct_resolution": True,
    },
    {
        "id": "2",
        "label": "Edge case — 31 days (just outside 30-day window)",
        "message": (
            "I bought a defective product 31 days ago — just one day outside your 30-day window. "
            "I know it's tight but it truly was defective from the start. Can I still get a refund?"
        ),
        "ground_truth_policy": None,   # policy doesn't cover this; should escalate or deny
        "correct_resolution": False,   # agent will likely still try to resolve — confidently wrong
    },
    {
        "id": "3",
        "label": "Ambiguous case (shipping delay + defect combined)",
        "message": (
            "My package arrived 12 days late AND the item inside was broken. "
            "What am I entitled to?"
        ),
        "ground_truth_policy": "both_apply",  # both standard_refund + shipping_delay
        "correct_resolution": None,   # partial credit for citing both
    },
]


def run_confidence_test():
    print("\n[2] Confidence score unreliability demo")
    print("-" * 60)
    print("  Self-reported confidence vs. actual correctness\n")

    for case in CONFIDENCE_TEST_CASES:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            tools=SUPPORT_TOOLS,
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": case["message"]}],
        )

        tool_block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        tool_name = tool_block.name if tool_block else "NONE"
        tool_input = tool_block.input if tool_block else {}

        confidence = tool_input.get("confidence", "N/A")
        policy_applied = tool_input.get("policy_applied", "N/A")

        print(f"  Case {case['id']}: {case['label']}")
        print(f"  Tool called     : {tool_name}")
        print(f"  Policy applied  : {policy_applied}")
        print(f"  Self-confidence : {confidence}")
        print(f"  Ground truth    : {case['ground_truth_policy']}")
        if case["correct_resolution"] is False:
            print("  !! Expected escalation or denial — high confidence here = WRONG")
        elif case["correct_resolution"] is None:
            print("  !! Partial credit — check if BOTH policies are cited")
        print()

    print("  KEY INSIGHT:")
    print("  Models report high confidence based on familiarity with similar inputs,")
    print("  NOT based on whether they are actually correct.")
    print("  The 31-day edge case is the classic failure: just outside policy scope,")
    print("  model confidently applies the nearby policy anyway.")
    print("  Never use confidence scores alone as escalation triggers.")


# ---------------------------------------------------------------------------
# SECTION 3: Aggregate vs. stratified accuracy — the metrics trap
#
# Simulate extraction results across 3 document types.
# Aggregate: 97% looks fine. Stratified: one type has 40% error.
# ---------------------------------------------------------------------------

SIMULATED_EXTRACTION_RESULTS = [
    # (doc_type, extracted_value, ground_truth, correct)
    # Type A: invoices — high accuracy
    *[("invoice", "correct", "correct", True) for _ in range(60)],
    *[("invoice", "wrong", "correct", False) for _ in range(5)],
    # Type B: contracts — medium accuracy
    *[("contract", "correct", "correct", True) for _ in range(25)],
    *[("contract", "wrong", "correct", False) for _ in range(5)],
    # Type C: handwritten forms — very low accuracy (but small sample)
    *[("handwritten_form", "correct", "correct", True) for _ in range(3)],
    *[("handwritten_form", "wrong", "correct", False) for _ in range(2)],
]


def compute_accuracy(results: list[tuple]) -> dict:
    """Compute aggregate + per-type accuracy from simulation results."""
    total = len(results)
    correct_total = sum(1 for r in results if r[3])
    aggregate = correct_total / total

    by_type = {}
    for doc_type, _, _, is_correct in results:
        if doc_type not in by_type:
            by_type[doc_type] = {"correct": 0, "total": 0}
        by_type[doc_type]["total"] += 1
        if is_correct:
            by_type[doc_type]["correct"] += 1

    stratified = {
        t: round(v["correct"] / v["total"], 3)
        for t, v in by_type.items()
    }

    return {
        "aggregate_accuracy": round(aggregate, 3),
        "stratified_accuracy": stratified,
        "per_type_counts": {
            t: {"n": v["total"], "errors": v["total"] - v["correct"]}
            for t, v in by_type.items()
        },
    }


def run_metrics_trap_demo():
    print("\n[3] Aggregate vs. stratified accuracy — the metrics trap")
    print("-" * 60)

    metrics = compute_accuracy(SIMULATED_EXTRACTION_RESULTS)

    print(f"\n  Aggregate accuracy  : {metrics['aggregate_accuracy'] * 100:.1f}%  ← 'looks good'")
    print(f"\n  Stratified accuracy by document type:")
    for doc_type, acc in metrics["stratified_accuracy"].items():
        n = metrics["per_type_counts"][doc_type]["n"]
        errors = metrics["per_type_counts"][doc_type]["errors"]
        flag = "  ← HIDDEN FAILURE" if acc < 0.8 else ""
        print(f"    {doc_type:<20} {acc * 100:.1f}%   (n={n}, errors={errors}){flag}")

    print()
    print("  KEY INSIGHT:")
    print("  Aggregate accuracy buries minority-class failures.")
    print("  A 97% overall rate can coexist with a 40% error rate on one document type.")
    print("  Stratified sampling by document type, category, or input subgroup is")
    print("  required to surface these failures before they reach production.")
    print()
    print("  For the exam: 'stratified sampling' = separate accuracy per subgroup,")
    print("  not sampling fewer items overall.")


# ---------------------------------------------------------------------------
# SECTION 4: Run everything
# ---------------------------------------------------------------------------

def run_all():
    print("=" * 70)
    print("ESCALATION PATTERNS & HUMAN-IN-THE-LOOP")
    print("=" * 70)

    run_escalation_cases()
    run_confidence_test()
    run_metrics_trap_demo()

    print("=" * 70)
    print("WHAT TO OBSERVE ACROSS ALL SECTIONS")
    print("=" * 70)
    print("""
Section 1 — Escalation triggers:
  Frustrated customer (Case A): agent should resolve, not escalate.
    Sentiment = signal. Policy coverage + empathy = correct response.
    Escalating here wastes human agent capacity on a routine refund.
  Explicit human request (Case B): no discretion — must escalate immediately.
    The exam tests that this trigger overrides everything else.
  Policy gap (Case C): complex multi-part request no single policy covers.
    Agent must NOT invent rules. Escalate with reason='policy_gap'.

Section 2 — Confidence unreliability:
  Clear-cut case: high confidence + correct resolution → confidence looks useful.
  31-day edge case: high confidence + WRONG resolution → the silent failure mode.
    The model "knows" the 30-day refund policy well, so it generalizes to 31 days.
    It reports high confidence because similar-looking inputs are familiar.
    An escalation trigger based on confidence score would NOT catch this.
  Implication: confidence scores are useful for sorting tasks, not for safety gates.

Section 3 — Metrics trap:
  97% aggregate accuracy misleads — it includes easy invoices that inflate the number.
  Handwritten forms (rare, hard) have 40% error — invisible in aggregate stats.
  Stratified sampling: split the evaluation dataset by document type BEFORE reporting.
  Exam trap: "our pipeline is 97% accurate" is never a complete answer.
""")


# ---------------------------------------------------------------------------
# REFLECTION QUESTIONS (answer in learnings.md)
# ---------------------------------------------------------------------------

REFLECTION = """
REFLECTION QUESTIONS — answer in learnings.md
==============================================

1. A customer says "I'm extremely frustrated with this service." Should the agent
   escalate? Why or why not?

2. A customer says "Just give me a human." What does the agent do next?

3. Why are self-reported confidence scores unreliable as escalation triggers?

4. Your extraction pipeline reports 97% accuracy. Why might this be misleading?

5. What is stratified sampling and why is it better than aggregate accuracy metrics?
"""


if __name__ == "__main__":
    # Uncomment to run the live demo (uses API credits):
    # run_all()

    print(REFLECTION)
    print(
        "\nKey rules:\n"
        "  Frustrated + policy-covered → resolve with empathy, do NOT escalate\n"
        "  Explicit human request      → always escalate immediately\n"
        "  Policy gap                  → escalate with reason='policy_gap'\n"
        "  Confidence scores           → correlate with familiarity, NOT accuracy\n"
        "  Aggregate 97%               → check stratified accuracy per subgroup"
    )
