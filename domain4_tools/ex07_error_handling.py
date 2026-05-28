"""
Domain 4 Exercise 7: Structured Error Responses
=================================================
CCA-F Topic: Tool Design & MCP Integration

Key concepts:
  - 4 error categories — each requires a DIFFERENT recovery action:
      transient   → retry with backoff (network blip, timeout, rate limit)
      validation  → fix the input, then retry (bad format, missing field)
      business    → do NOT retry; route to alternative workflow (policy violation)
      permission  → escalate to human; do not retry (403, auth failure)

  - Access failure vs. valid empty result:
      Access failure = tool could not run  → error
      Empty result   = tool ran, found nothing → success with empty data
      Confusing these breaks recovery logic: retrying an empty result wastes
      calls; treating an access failure as empty hides a real problem.

  - Structured error context — a good error response includes:
      1. error_type  (one of the 4 categories above)
      2. message     (what went wrong, human-readable)
      3. attempted   (what the tool tried to do)
      4. partial_results (any data collected before failure, if any)
      5. alternatives (suggested next steps)

  - Two anti-patterns to avoid:
      Silent suppression  → tool returns success but hides a failure;
                            the agent proceeds on bad data
      Hard termination    → any error aborts the entire workflow;
                            partial results are discarded unnecessarily

THE EXERCISE:
  Part A — Simulated tool with all 4 error types + valid empty result.
    Inspect the structured error payloads.

  Part B — Recovery loop. Claude receives a task, calls the tool,
    and the loop handles each error type correctly:
      transient   → automatic retry (up to 3x with backoff)
      validation  → send error back to Claude so it can fix its input
      business    → inject an alternative-workflow message and continue
      permission  → stop and escalate (print escalation notice)

  Part C — Anti-pattern demo.
    Version 1: silent suppression (agent never knows a subagent failed).
    Version 2: hard termination (one transient error kills everything).
    Compare to Part B's graceful recovery.

Run: python ex07_error_handling.py
"""

import anthropic
import json
import time
import random

client = anthropic.Anthropic()


# ---------------------------------------------------------------------------
# Simulated tool: fetch_order_data
# ---------------------------------------------------------------------------
# Takes an order_id and a forced_error parameter so we can test all paths.
# In a real system, errors come from the outside world — here we inject them.

def fetch_order_data(order_id: str, forced_error: str | None = None) -> dict:
    """
    Simulated tool implementation.
    Returns structured data OR a structured error — never raises an exception.
    Tools should ALWAYS return structured responses, not raise.
    """

    # Valid empty result — tool worked, nothing matched
    if order_id == "ORDER_NONE":
        return {
            "success": True,
            "data": [],           # empty list is valid — not an error
            "message": "No orders found matching the criteria."
        }

    # Transient error — temporary failure, safe to retry
    if forced_error == "transient" or (forced_error is None and order_id == "ORDER_TRANS"):
        return {
            "success": False,
            "error_type": "transient",
            "message": "Database connection timed out. The service is temporarily unavailable.",
            "attempted": f"Order lookup by id '{order_id}'",
            "partial_results": None,
            "alternatives": ["Retry after a short delay."]
        }

    # Validation error — bad input, Claude must fix it before retrying
    if forced_error == "validation" or (forced_error is None and order_id == "ORDER_BAD"):
        return {
            "success": False,
            "error_type": "validation",
            "message": "Invalid order_id format. Expected format: ORD-XXXXXX (e.g. ORD-123456).",
            "attempted": f"Order lookup by id '{order_id}'",
            "partial_results": None,
            "alternatives": ["Correct the order_id format and retry."]
        }

    # Business rule error — do NOT retry; policy prevents this action
    if forced_error == "business" or (forced_error is None and order_id == "ORDER_BIZ"):
        return {
            "success": False,
            "error_type": "business",
            "message": "Order ORD-999 was placed more than 90 days ago. Refund window has closed.",
            "attempted": f"Refund eligibility check for order '{order_id}'",
            "partial_results": {"order_id": order_id, "days_since_order": 97},
            "alternatives": [
                "Offer a store credit instead of a refund.",
                "Escalate to the exceptions team if customer has special status."
            ]
        }

    # Permission error — stop, do not retry, escalate
    if forced_error == "permission" or (forced_error is None and order_id == "ORDER_AUTH"):
        return {
            "success": False,
            "error_type": "permission",
            "message": "Access denied. This order belongs to a different account region and requires elevated permissions.",
            "attempted": f"Cross-region order lookup for '{order_id}'",
            "partial_results": None,
            "alternatives": ["Escalate to a human agent with cross-region access."]
        }

    # Happy path
    return {
        "success": True,
        "data": {
            "order_id": order_id,
            "customer": "Jane Smith",
            "amount": 149.99,
            "status": "delivered",
            "date": "2026-03-15"
        }
    }


# ---------------------------------------------------------------------------
# Tool definition for the Claude API
# ---------------------------------------------------------------------------

TOOL_DEF = {
    "name": "fetch_order_data",
    "description": (
        "Retrieve order details from the order management system by order ID. "
        "Returns order data on success, or a structured error with error_type, "
        "message, attempted action, partial_results, and alternatives. "
        "Use this to look up customer orders before processing refunds or changes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "The order ID in format ORD-XXXXXX, e.g. 'ORD-123456'."
            }
        },
        "required": ["order_id"]
    }
}


# ---------------------------------------------------------------------------
# PART A — Inspect structured error payloads
# ---------------------------------------------------------------------------

def part_a_inspect_errors():
    print("\n" + "="*60)
    print("PART A: Structured error payloads")
    print("="*60)

    test_cases = [
        ("ORD-123456",  None,          "Happy path"),
        ("ORDER_NONE",  None,          "Valid empty result (no match)"),
        ("ORDER_TRANS", None,          "Transient error"),
        ("ORDER_BAD",   None,          "Validation error"),
        ("ORDER_BIZ",   None,          "Business rule error"),
        ("ORDER_AUTH",  None,          "Permission error"),
    ]

    for order_id, forced, label in test_cases:
        result = fetch_order_data(order_id, forced)
        print(f"\n--- {label} ---")
        print(json.dumps(result, indent=2))

    print("\nKEY OBSERVATION:")
    print("  Empty result (ORDER_NONE): success=True, data=[]")
    print("  Access failure (ORDER_TRANS): success=False, error_type='transient'")
    print("  These look different. Confusing them breaks recovery logic.")


# ---------------------------------------------------------------------------
# PART B — Recovery loop
# ---------------------------------------------------------------------------

RECOVERY_SYSTEM_PROMPT = """You are a customer support agent that can look up order details.

When you call fetch_order_data and receive an error, read the error_type carefully:
  - transient:   The system will retry automatically. Wait for the retry result.
  - validation:  Your order_id format was wrong. Fix it based on the error message and retry.
  - business:    Do NOT retry. Acknowledge the policy and follow the alternatives provided.
  - permission:  Do NOT retry. Tell the user this requires escalation to a human agent.

When success=True and data=[], tell the user no matching orders were found — this is not an error."""

def execute_tool_with_recovery(tool_input: dict, scenario: str) -> dict:
    """
    Wraps fetch_order_data with the recovery logic.
    Returns the tool result to feed back to Claude.
    Handles transient retries here (programmatically) — not by asking Claude to retry.
    """
    order_id = tool_input.get("order_id", "")

    # Map scenario to forced error for demo purposes
    forced_map = {
        "transient": "transient",
        "validation": "validation",
        "business": "business",
        "permission": "permission",
        "empty": None,   # ORDER_NONE path
        "happy": None,
    }
    forced = forced_map.get(scenario)

    # Transient: retry up to 3 times with backoff (programmatic — not Claude's job)
    if scenario == "transient":
        for attempt in range(1, 4):
            print(f"  [Recovery] Transient error — attempt {attempt}/3...")
            result = fetch_order_data(order_id, "transient")
            if attempt == 3:
                # Simulate recovery on 3rd attempt
                result = fetch_order_data("ORD-123456", None)
                print(f"  [Recovery] Attempt {attempt} succeeded.")
            else:
                time.sleep(0.3)  # backoff (short for demo)
        return result

    # Permission: stop immediately, do not retry
    if scenario == "permission":
        result = fetch_order_data(order_id, "permission")
        print("  [Recovery] Permission error — stopping. Escalation required.")
        return result

    return fetch_order_data(order_id, forced)


def part_b_recovery_loop(scenario: str, user_message: str):
    """
    Full agentic loop with error-type-aware recovery.
    scenario: one of 'happy', 'empty', 'transient', 'validation', 'business', 'permission'
    """
    print(f"\n{'='*60}")
    print(f"PART B: Recovery loop — scenario: {scenario.upper()}")
    print(f"{'='*60}")
    print(f"User: {user_message}")

    messages = [{"role": "user", "content": user_message}]

    for turn in range(6):  # cap at 6 turns to avoid runaway loops
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=500,
            system=RECOVERY_SYSTEM_PROMPT,
            tools=[TOOL_DEF],
            tool_choice={"type": "auto"},
            messages=messages
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Extract final text
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"\nClaude: {block.text}")
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"\n  [Tool call] {block.name}({json.dumps(block.input)})")
                    result = execute_tool_with_recovery(block.input, scenario)
                    print(f"  [Tool result] {json.dumps(result)}")

                    # Permission error: inject escalation signal into result
                    # so Claude knows to stop and escalate
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            messages.append({"role": "user", "content": tool_results})


# ---------------------------------------------------------------------------
# PART C — Anti-pattern demo
# ---------------------------------------------------------------------------

def part_c_antipatterns():
    print("\n" + "="*60)
    print("PART C: Anti-patterns")
    print("="*60)

    # Anti-pattern 1: Silent suppression
    print("\n--- Anti-pattern 1: SILENT SUPPRESSION ---")
    print("Tool fails with a transient error.")
    print("Agent swallows the error and returns empty data as if nothing happened.\n")

    def suppressed_fetch(order_id):
        result = fetch_order_data(order_id, "transient")
        if not result["success"]:
            # BAD: return empty success instead of propagating the error
            return {"success": True, "data": []}
        return result

    suppressed = suppressed_fetch("ORD-123456")
    print(f"Suppressed result: {json.dumps(suppressed, indent=2)}")
    print("Problem: caller sees success=True, data=[] and concludes 'no orders found'.")
    print("         The real cause (timeout) is invisible. Recovery is impossible.")

    # Anti-pattern 2: Hard termination
    print("\n--- Anti-pattern 2: HARD TERMINATION ---")
    print("Processing 3 orders. One gets a transient error.")
    print("Hard termination aborts everything — even the 2 that succeeded.\n")

    orders = ["ORD-111111", "ORDER_TRANS", "ORD-333333"]
    results = []

    try:
        for oid in orders:
            r = fetch_order_data(oid)
            if not r["success"]:
                raise RuntimeError(f"Tool failed for {oid}: {r['message']}")  # BAD
            results.append(r["data"])
            print(f"  Processed {oid}: OK")
    except RuntimeError as e:
        print(f"  ABORTED: {e}")
        print(f"  Results collected before abort: {len(results)}/3")

    print("\nProblem: 2 orders processed successfully but their results are discarded.")
    print("         Graceful degradation would return partial results + flag the failure.")

    # Graceful degradation (contrast)
    print("\n--- Graceful degradation (contrast) ---")
    results = []
    errors = []
    for oid in orders:
        r = fetch_order_data(oid)
        if r["success"]:
            results.append(r.get("data", []))
        else:
            errors.append({"order_id": oid, "error": r["error_type"], "message": r["message"]})

    print(f"  Succeeded: {len(results)}/3 orders")
    print(f"  Failed:    {len(errors)}/3 orders")
    for e in errors:
        print(f"    {e['order_id']}: [{e['error']}] {e['message']}")
    print("  Caller receives partial results AND clear attribution of what failed and why.")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Exercise 7: Structured Error Responses")
    print("========================================")
    print("Choose which part to run:")
    print("  A        — Inspect the 4 error types + empty result payloads")
    print("  B-happy  — Recovery loop: happy path")
    print("  B-empty  — Recovery loop: valid empty result (not an error)")
    print("  B-trans  — Recovery loop: transient error → auto-retry")
    print("  B-val    — Recovery loop: validation error → Claude fixes input")
    print("  B-biz    — Recovery loop: business error → alternative workflow")
    print("  B-perm   — Recovery loop: permission error → escalation")
    print("  C        — Anti-patterns: silent suppression + hard termination")
    print("  all      — Run everything in sequence")

    choice = input("\nEnter choice: ").strip().lower()

    if choice in ("a", "all"):
        part_a_inspect_errors()

    b_scenarios = {
        "b-happy": ("happy", "Can you look up order ORD-123456 for me?"),
        "b-empty": ("empty", "Can you look up order ORDER_NONE for me?"),
        "b-trans": ("transient", "Can you look up order ORD-123456 for me?"),
        "b-val":   ("validation", "Can you look up order ORDER_BAD for me?"),
        "b-biz":   ("business", "I'd like a refund on order ORDER_BIZ."),
        "b-perm":  ("permission", "Can you pull up order ORDER_AUTH?"),
    }

    if choice == "all":
        for key, (scenario, msg) in b_scenarios.items():
            part_b_recovery_loop(scenario, msg)
    elif choice in b_scenarios:
        scenario, msg = b_scenarios[choice]
        part_b_recovery_loop(scenario, msg)

    if choice in ("c", "all"):
        part_c_antipatterns()

    if choice not in ("a", "c", "all") and choice not in b_scenarios:
        print("Unknown choice.")

    print("\n" + "="*60)
    print("REFLECTION QUESTIONS (answer in learnings.md):")
    print("="*60)
    print("""
1. A refund API returns 403 because the user's account lacks permissions.
   What error category is this? Retryable?

2. A search tool returns an empty list because no results matched.
   Is this an error? How should it be structured?

3. What is the difference between "silent suppression" and a useful
   error response?

4. An agent retries a business-rule violation 3 times. What's wrong
   with this approach?

5. What fields should a structured error response always include?
""")
