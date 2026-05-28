"""
Domain 5 Exercise 17: Error Propagation in Multi-Agent Systems
CCA-F Topic: Context Management & Reliability

KEY CONCEPTS
============
1. Structured error context — what a failing subagent MUST return:
   — failure_type: transient | validation | business | permission
   — what_was_attempted: the specific operation that failed
   — partial_results: any data successfully retrieved before the failure
   — alternatives: suggested next steps or fallback paths

2. Silent suppression anti-pattern:
   — Coordinator catches the subagent failure internally and returns a "success" response
   — The user (or next agent) sees complete-looking output built on missing data
   — Downstream agents make decisions on incomplete information without knowing it
   — Debugging is impossible: no signal that anything went wrong

3. Hard termination anti-pattern:
   — Any single subagent failure causes the ENTIRE workflow to abort
   — Partial results from successful subagents are discarded unnecessarily
   — Leaves the user with nothing when they could have had partial value

4. Access failure vs. valid empty result:
   — Access failure: the tool/API could not be reached or returned an error
     → structured error response required; triggers recovery logic
   — Valid empty result: the tool ran successfully but found nothing matching
     → success=True, empty data, informative message; no error handling needed
   — Confusing them breaks recovery: retrying a valid empty result wastes tokens;
     silently swallowing an access failure hides real data loss

5. Graceful degradation:
   — Return partial results from successful subagents
   — Clearly attribute which subagent failed, why, and what was attempted
   — Suggest alternatives or next steps
   — The user/coordinator gets maximum value even when the system is partially down

EXERCISE STRUCTURE
==================
Section 1 — Silent suppression: one subagent fails; coordinator hides it
Section 2 — Hard termination: one subagent fails; entire workflow aborts
Section 3 — Graceful degradation: one subagent fails; partial results + clear error context
Section 4 — Access failure vs. valid empty result: same tool, two different scenarios
"""

import anthropic
import json
import random

client = anthropic.Anthropic()


# ---------------------------------------------------------------------------
# Simulated subagent: research one company
# company_id controls whether it fails and how
# ---------------------------------------------------------------------------

COMPANY_DATA = {
    "AAPL": {
        "name": "Apple Inc.",
        "revenue_bn": 383.3,
        "employees": 161_000,
        "sector": "Technology",
        "summary": "Consumer electronics and software giant with strong services growth.",
    },
    "GOOG": {
        "name": "Alphabet Inc.",
        "revenue_bn": 307.4,
        "employees": 182_000,
        "sector": "Technology",
        "summary": "Search and advertising leader expanding into cloud and AI.",
    },
    "MSFT": {
        "name": "Microsoft Corp.",
        "revenue_bn": 245.1,
        "employees": 221_000,
        "sector": "Technology",
        "summary": "Enterprise software and cloud platform with Azure driving growth.",
    },
}

# Failure modes controlled per company_id for demo purposes
FAILURE_CONFIG = {
    # AAPL always succeeds
    "AAPL": None,
    # GOOG will fail with a transient error (simulate a network timeout)
    "GOOG": {
        "failure_type": "transient",
        "what_was_attempted": "Fetching financial data from market data API for GOOG",
        "partial_results": None,
        "alternatives": [
            "Retry after 30 seconds",
            "Use cached data from last known snapshot (may be stale)",
        ],
        "message": "Connection timed out after 10s — market data API unreachable",
    },
    # MSFT always succeeds
    "MSFT": None,
}


def research_company(company_id: str) -> dict:
    """
    Simulated subagent: looks up a company.
    Returns structured result (success or error) — never raises an exception.
    """
    failure = FAILURE_CONFIG.get(company_id)

    if failure:
        return {
            "success": False,
            "company_id": company_id,
            "error": failure,
        }

    if company_id not in COMPANY_DATA:
        # Valid empty result — company not in our dataset, not an access failure
        return {
            "success": True,
            "company_id": company_id,
            "data": None,
            "message": f"No data found for company_id '{company_id}' — not in dataset",
        }

    return {
        "success": True,
        "company_id": company_id,
        "data": COMPANY_DATA[company_id],
    }


# ---------------------------------------------------------------------------
# SECTION 1: Silent suppression
#
# Coordinator runs 3 subagents. GOOG fails. Coordinator swallows the failure,
# synthesizes from only 2 results, but presents the output as if all 3 succeeded.
# ---------------------------------------------------------------------------

def coordinator_silent_suppression(companies: list[str]) -> dict:
    """
    Anti-pattern: catch failures, pretend they didn't happen.
    """
    all_data = {}
    for company_id in companies:
        result = research_company(company_id)
        if result["success"] and result.get("data"):
            all_data[company_id] = result["data"]
        # Failure silently dropped — no logging, no flag, no mention

    # Build a summary — looks complete, is not
    summary_lines = []
    for cid, data in all_data.items():
        summary_lines.append(
            f"{data['name']}: ${data['revenue_bn']}B revenue, {data['employees']:,} employees"
        )

    return {
        "status": "complete",
        "companies_analyzed": list(all_data.keys()),
        "summary": "\n".join(summary_lines),
        # No indication that GOOG was silently dropped
    }


# ---------------------------------------------------------------------------
# SECTION 2: Hard termination
#
# Coordinator runs subagents. First failure aborts everything.
# AAPL result is discarded even though it succeeded.
# ---------------------------------------------------------------------------

def coordinator_hard_termination(companies: list[str]) -> dict:
    """
    Anti-pattern: abort entire workflow on first subagent failure.
    """
    results = {}
    for company_id in companies:
        result = research_company(company_id)
        if not result["success"]:
            # Hard stop — throw away everything collected so far
            raise RuntimeError(
                f"Subagent for {company_id} failed: "
                f"{result['error']['message']}. Aborting workflow."
            )
        if result.get("data"):
            results[company_id] = result["data"]

    return {"status": "complete", "data": results}


# ---------------------------------------------------------------------------
# SECTION 3: Graceful degradation — the correct pattern
#
# Coordinator collects all results, separates successes from failures,
# returns partial data with clear attribution and alternatives.
# ---------------------------------------------------------------------------

def coordinator_graceful_degradation(companies: list[str]) -> dict:
    """
    Correct pattern: partial results + structured error attribution.
    """
    successes = {}
    failures = []

    for company_id in companies:
        result = research_company(company_id)
        if result["success"] and result.get("data"):
            successes[company_id] = result["data"]
        elif not result["success"]:
            failures.append({
                "company_id": company_id,
                "error": result["error"],
            })
        # Valid empty result (data=None, success=True) handled separately:
        elif result["success"] and result.get("data") is None:
            failures.append({
                "company_id": company_id,
                "error": {
                    "failure_type": "not_found",
                    "message": result.get("message", "No data available"),
                    "what_was_attempted": f"Lookup for {company_id}",
                    "partial_results": None,
                    "alternatives": ["Verify company_id is correct"],
                },
            })

    # Build output
    output = {
        "status": "partial" if failures else "complete",
        "companies_analyzed": list(successes.keys()),
        "companies_failed": [f["company_id"] for f in failures],
    }

    # Summarize what succeeded
    if successes:
        summary_lines = []
        for cid, data in successes.items():
            summary_lines.append(
                f"{data['name']}: ${data['revenue_bn']}B revenue, "
                f"{data['employees']:,} employees — {data['summary']}"
            )
        output["summary"] = "\n".join(summary_lines)

    # Structured error context for each failure
    if failures:
        output["error_details"] = failures
        output["note"] = (
            f"{len(failures)} subagent(s) failed. "
            "Partial results above are complete for the companies listed. "
            "See error_details for failure context and alternatives."
        )

    return output


# ---------------------------------------------------------------------------
# SECTION 4: Access failure vs. valid empty result
#
# Same tool (search_customer_records), two scenarios:
#   Scenario A: DB unreachable → access failure → triggers recovery
#   Scenario B: DB reachable, no matching records → valid empty → no retry
# ---------------------------------------------------------------------------

def search_customer_records(customer_id: str, scenario: str) -> dict:
    """
    Simulated tool that can return either an access failure or a valid empty result.
    scenario: 'access_failure' | 'valid_empty' | 'found'
    """
    if scenario == "access_failure":
        return {
            "success": False,
            "error": {
                "failure_type": "transient",
                "what_was_attempted": f"SELECT * FROM customers WHERE id='{customer_id}'",
                "partial_results": None,
                "alternatives": [
                    "Retry in 10 seconds",
                    "Query read replica at replica.db.internal",
                ],
                "message": "Database connection pool exhausted — all 50 connections in use",
            },
        }

    if scenario == "valid_empty":
        return {
            "success": True,
            "customer_id": customer_id,
            "records": [],
            "message": f"Query succeeded — no records found for customer_id '{customer_id}'",
        }

    # scenario == "found"
    return {
        "success": True,
        "customer_id": customer_id,
        "records": [
            {"order_id": "ORD-9912", "amount": 149.99, "status": "delivered"},
            {"order_id": "ORD-9876", "amount": 89.00, "status": "refunded"},
        ],
    }


def demonstrate_access_vs_empty():
    """Show how agent recovery logic differs based on result type."""
    print("\n[4] Access failure vs. valid empty result")
    print("-" * 60)

    for scenario, label in [
        ("access_failure", "DB unreachable (access failure)"),
        ("valid_empty", "DB up, customer not found (valid empty)"),
        ("found", "DB up, records found"),
    ]:
        result = search_customer_records("CUST-00123", scenario)

        print(f"\n  Scenario: {label}")
        print(f"  success={result['success']}")

        if not result["success"]:
            err = result["error"]
            print(f"  → RECOVERY: Retry (type={err['failure_type']})")
            print(f"  → what_was_attempted: {err['what_was_attempted']}")
            print(f"  → alternatives: {err['alternatives']}")
        elif result["success"] and not result.get("records"):
            print(f"  → NO RETRY: {result.get('message', 'empty result')}")
            print(f"  → This is a valid result — the customer simply has no records")
        else:
            print(f"  → Records found: {len(result['records'])} order(s)")

    print()
    print("  KEY INSIGHT:")
    print("  Access failure: success=False → recovery logic fires (retry/escalate)")
    print("  Valid empty   : success=True, records=[] → no retry, just inform the user")
    print("  Confusion between the two breaks recovery logic in both directions:")
    print("    - Retrying a valid empty result wastes tokens and adds latency")
    print("    - Swallowing an access failure silently hides real data loss")


# ---------------------------------------------------------------------------
# SECTION 5: Run everything
# ---------------------------------------------------------------------------

COMPANIES = ["AAPL", "GOOG", "MSFT"]


def run_all():
    print("=" * 70)
    print("ERROR PROPAGATION IN MULTI-AGENT SYSTEMS")
    print("=" * 70)

    # --- Section 1: Silent suppression ---
    print("\n[1] Silent suppression — GOOG fails, coordinator hides it")
    print("-" * 60)
    result_v1 = coordinator_silent_suppression(COMPANIES)
    print(f"  Status reported   : {result_v1['status']}")
    print(f"  Companies in output: {result_v1['companies_analyzed']}")
    print(f"  Summary:\n    {result_v1['summary']}")
    print()
    print("  !! GOOG is missing from output — no signal that it failed.")
    print("  !! User assumes all 3 companies were analyzed.")

    # --- Section 2: Hard termination ---
    print("\n[2] Hard termination — GOOG fails, entire workflow aborts")
    print("-" * 60)
    try:
        result_v2 = coordinator_hard_termination(COMPANIES)
        print(f"  Result: {result_v2}")
    except RuntimeError as e:
        print(f"  WORKFLOW ABORTED: {e}")
        print()
        print("  !! AAPL succeeded but its result was discarded.")
        print("  !! User gets nothing when they could have had partial value.")

    # --- Section 3: Graceful degradation ---
    print("\n[3] Graceful degradation — partial results + structured error")
    print("-" * 60)
    result_v3 = coordinator_graceful_degradation(COMPANIES)
    print(f"  Status            : {result_v3['status']}")
    print(f"  Succeeded         : {result_v3['companies_analyzed']}")
    print(f"  Failed            : {result_v3['companies_failed']}")
    print(f"  Summary:\n    {result_v3.get('summary', 'N/A')}")
    print(f"  Note: {result_v3.get('note', '')}")
    print(f"  Error details:")
    for err_entry in result_v3.get("error_details", []):
        err = err_entry["error"]
        print(f"    {err_entry['company_id']}: [{err['failure_type']}] {err['message']}")
        print(f"      Alternatives: {err['alternatives']}")

    # --- Section 4: Access failure vs. valid empty ---
    demonstrate_access_vs_empty()

    print("\n" + "=" * 70)
    print("WHAT TO OBSERVE")
    print("=" * 70)
    print("""
Version 1 — Silent suppression:
  Output looks complete (status='complete', 2 company summaries).
  No signal that GOOG failed. Downstream agents or users see a clean result
  built on incomplete data. Debugging is impossible — no failure footprint.

Version 2 — Hard termination:
  AAPL result is discarded because GOOG failed later in the loop.
  User receives nothing. The exception propagates upward — likely surfaces
  as a 500 error or an unhelpful "something went wrong" message.

Version 3 — Graceful degradation (correct):
  status='partial' signals incompleteness immediately.
  AAPL and MSFT summaries are returned — real value delivered.
  GOOG failure attributed clearly: failure_type, what_was_attempted, alternatives.
  Coordinator gives the human (or next agent) everything needed to decide:
    "retry GOOG in 30s" or "proceed without GOOG" — informed choice, not blind failure.

Section 4 — Access failure vs. valid empty:
  The test for access failure is success=False.
  The test for valid empty is success=True + empty collection.
  Never mix them: don't return success=False for "no records found",
  and never return success=True with an error message buried in the body.
""")


# ---------------------------------------------------------------------------
# REFLECTION QUESTIONS (answer in learnings.md)
# ---------------------------------------------------------------------------

REFLECTION = """
REFLECTION QUESTIONS — answer in learnings.md
==============================================

1. What 4 pieces of information should a structured error response always include?

2. A database subagent returns an empty list because no records matched the query.
   Is this an error? How should it be structured?

3. How is "silent suppression" harmful in a multi-agent system?

4. How is "hard termination on any subagent failure" harmful?

5. What is the difference between "access failure" and "valid empty result"
   and why does confusing them break recovery logic?
"""


if __name__ == "__main__":
    # Uncomment to run the live demo (no API credits needed — all simulated):
    # run_all()

    print(REFLECTION)
    print(
        "\nKey rules:\n"
        "  Silent suppression   → never hide failures; always propagate error context\n"
        "  Hard termination     → never abort on one failure; return partial results\n"
        "  Structured error     → failure_type + what_attempted + partial_results + alternatives\n"
        "  Access failure       → success=False → triggers retry/escalation\n"
        "  Valid empty result   → success=True, empty data → no retry, just inform"
    )
