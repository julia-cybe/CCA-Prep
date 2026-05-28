"""
Domain 3 Exercise 14: Batch API vs. Synchronous API
CCA-F Topic: Prompt Engineering & Structured Output

KEY CONCEPTS
============
1. Message Batches API:
   - 50% cost savings vs. synchronous
   - Up to 24-hour processing window (no latency SLA)
   - Results retrieved via polling or result_url after batch completes
   - Suited for latency-tolerant, high-volume, overnight workloads
2. `custom_id`: caller-assigned identifier per request (max 64 chars)
   — the ONLY way to correlate batch results back to source documents
   — results arrive out of order; custom_id is your join key
3. NO multi-turn tool calling within a single batch request:
   — each batch request is exactly one user turn → one assistant response
   — if you need tool results fed back, that's a second round-trip = new batch
4. Decision rule:
   - Synchronous  → user is waiting, real-time response required (< 30s)
   - Batch API    → latency-tolerant, large volume, cost matters
5. Multi-instance review: a separate Claude instance catches more errors than
   the same instance reviewing its own output — self-review is anchored to the
   original reasoning and misses the same blind spots

EXERCISE STRUCTURE
==================
Section 1 — Synchronous baseline: process 5 documents one-by-one, measure time
Section 2 — Batch submission: submit same 5 documents as one batch, assign custom_ids
Section 3 — Poll + correlate: check batch status, retrieve results, join back to source
Section 4 — Multi-instance review: submit a second batch where each doc is reviewed
            by a fresh instance (not the same response) — contrast with self-review
"""

import time
import anthropic

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Sample support tickets to classify (small set for demonstration)
# ---------------------------------------------------------------------------

TICKETS = [
    {
        "id": "ticket_001",
        "text": "My invoice shows a double charge from last Tuesday. I need this fixed immediately.",
        "expected_category": "billing",
    },
    {
        "id": "ticket_002",
        "text": "I cannot log in — the app says my password is wrong but I just reset it.",
        "expected_category": "auth",
    },
    {
        "id": "ticket_003",
        "text": "The export to CSV feature is broken. It downloads an empty file every time.",
        "expected_category": "bug",
    },
    {
        "id": "ticket_004",
        "text": "How do I add a second user to my account? I need to onboard a colleague.",
        "expected_category": "how_to",
    },
    {
        "id": "ticket_005",
        "text": "I'd like to cancel my subscription at the end of this billing cycle.",
        "expected_category": "cancellation",
    },
]

CLASSIFY_PROMPT = """Classify this support ticket into exactly one category.

Categories: billing, auth, bug, how_to, cancellation, other

Respond with JSON only: {{"category": "<value>", "confidence": "high|medium|low", "summary": "<one sentence>"}}

Ticket:
{text}"""


# ---------------------------------------------------------------------------
# SECTION 1: Synchronous baseline — one-by-one, measure wall time
# ---------------------------------------------------------------------------

def classify_synchronous(tickets: list[dict]) -> list[dict]:
    """Process tickets sequentially. Each call blocks until response arrives."""
    results = []
    start = time.time()

    for ticket in tickets:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=128,
            messages=[
                {
                    "role": "user",
                    "content": CLASSIFY_PROMPT.format(text=ticket["text"]),
                }
            ],
        )
        results.append(
            {
                "ticket_id": ticket["id"],
                "response": response.content[0].text,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        )

    elapsed = time.time() - start
    return results, elapsed


# ---------------------------------------------------------------------------
# SECTION 2: Batch submission — all tickets in one API call
#
# Key points:
#  - custom_id must be unique within the batch; use ticket["id"] directly
#  - results arrive out of order — custom_id is the only join key
#  - the batch is processed asynchronously; this call returns immediately
# ---------------------------------------------------------------------------

def submit_batch(tickets: list[dict]) -> str:
    """Submit all tickets as a single batch. Returns batch_id."""
    requests = [
        anthropic.types.message_create_params.MessageCreateParamsNonStreaming(
            model="claude-haiku-4-5",
            max_tokens=128,
            messages=[
                {
                    "role": "user",
                    "content": CLASSIFY_PROMPT.format(text=ticket["text"]),
                }
            ],
            custom_id=ticket["id"],  # caller-assigned; used to correlate results
        )
        for ticket in tickets
    ]

    batch = client.messages.batches.create(requests=requests)
    print(f"Batch submitted: id={batch.id}  status={batch.processing_status}")
    print(f"  request_counts: {batch.request_counts}")
    return batch.id


# ---------------------------------------------------------------------------
# SECTION 3: Poll + correlate results back to source documents
#
# Batch status lifecycle: in_progress → ended
# Once ended, iterate client.messages.batches.results(batch_id)
# Each result has: custom_id, result.type ("succeeded"|"errored"|"expired")
# ---------------------------------------------------------------------------

def poll_until_complete(batch_id: str, poll_interval_seconds: int = 5) -> object:
    """Poll batch status until processing_status == 'ended'."""
    print(f"\nPolling batch {batch_id}...")
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        print(f"  status={batch.processing_status}  counts={batch.request_counts}")
        if batch.processing_status == "ended":
            return batch
        time.sleep(poll_interval_seconds)


def correlate_results(batch_id: str, source_tickets: list[dict]) -> list[dict]:
    """
    Retrieve batch results and join them back to source tickets using custom_id.
    Results arrive out of order — custom_id is the join key.
    """
    # Build a lookup from ticket_id → ticket for fast join
    ticket_by_id = {t["id"]: t for t in source_tickets}

    correlated = []
    for result in client.messages.batches.results(batch_id):
        ticket = ticket_by_id.get(result.custom_id, {})
        if result.result.type == "succeeded":
            msg = result.result.message
            correlated.append(
                {
                    "ticket_id": result.custom_id,
                    "expected_category": ticket.get("expected_category"),
                    "response": msg.content[0].text,
                    "input_tokens": msg.usage.input_tokens,
                    "output_tokens": msg.usage.output_tokens,
                }
            )
        else:
            correlated.append(
                {
                    "ticket_id": result.custom_id,
                    "error": result.result.type,
                }
            )

    return correlated


# ---------------------------------------------------------------------------
# SECTION 4: Multi-instance review
#
# Self-review limitation: when the same model instance reviews output it
# generated, it anchors to its original reasoning. It tends to agree with
# itself even when the output is wrong — the same blind spots apply.
#
# Multi-instance review: a FRESH request (new context, no memory of original)
# reviews the output. Different context → independent judgment → more corrections.
#
# Pattern: first batch generates classifications; second batch reviews them.
# Each review request gets: original ticket + proposed classification.
# This is two sequential batches, not one — the output of batch 1 feeds batch 2.
# ---------------------------------------------------------------------------

REVIEW_PROMPT = """You are reviewing a support ticket classification made by another system.

Original ticket:
{text}

Proposed classification:
{classification}

Is the classification correct? If not, what should it be?
Respond with JSON only: {{"correct": true/false, "correct_category": "<value or same>", "reason": "<one sentence>"}}"""


def submit_review_batch(tickets: list[dict], classifications: list[dict]) -> str:
    """Submit a second batch where a fresh instance reviews each classification."""
    ticket_by_id = {t["id"]: t for t in tickets}

    requests = [
        anthropic.types.message_create_params.MessageCreateParamsNonStreaming(
            model="claude-haiku-4-5",
            max_tokens=128,
            messages=[
                {
                    "role": "user",
                    "content": REVIEW_PROMPT.format(
                        text=ticket_by_id[c["ticket_id"]]["text"],
                        classification=c["response"],
                    ),
                }
            ],
            custom_id=f"review_{c['ticket_id']}",  # prefix avoids custom_id collision
        )
        for c in classifications
        if "response" in c  # skip errored results
    ]

    batch = client.messages.batches.create(requests=requests)
    print(f"\nReview batch submitted: id={batch.id}")
    return batch.id


# ---------------------------------------------------------------------------
# SECTION 5: Run the full workflow
# ---------------------------------------------------------------------------

def run_workflow():
    print("=" * 70)
    print("BATCH API WORKFLOW: Submit → Poll → Correlate → Review")
    print("=" * 70)

    # --- Synchronous baseline ---
    print("\n[1] Synchronous baseline (sequential, blocking)")
    sync_results, sync_elapsed = classify_synchronous(TICKETS)
    total_input = sum(r["input_tokens"] for r in sync_results)
    total_output = sum(r["output_tokens"] for r in sync_results)
    print(f"  Completed {len(sync_results)} tickets in {sync_elapsed:.1f}s")
    print(f"  Tokens: {total_input} input / {total_output} output")
    for r in sync_results:
        print(f"  {r['ticket_id']}: {r['response'][:80]}")

    # --- Batch classification ---
    print("\n[2] Batch submission")
    batch_id = submit_batch(TICKETS)

    print("\n[3] Polling for completion")
    poll_until_complete(batch_id)

    print("\n[4] Correlating results")
    classifications = correlate_results(batch_id, TICKETS)
    for c in classifications:
        if "response" in c:
            print(f"  {c['ticket_id']} (expected={c['expected_category']}): {c['response'][:80]}")
        else:
            print(f"  {c['ticket_id']}: ERROR — {c['error']}")

    # --- Multi-instance review batch ---
    print("\n[5] Multi-instance review batch")
    review_batch_id = submit_review_batch(TICKETS, classifications)

    print("\n[6] Polling review batch")
    poll_until_complete(review_batch_id)

    print("\n[7] Review results (fresh instance judgment)")
    for result in client.messages.batches.results(review_batch_id):
        if result.result.type == "succeeded":
            print(f"  {result.custom_id}: {result.result.message.content[0].text[:100]}")

    print("\n" + "=" * 70)
    print("WHAT TO OBSERVE")
    print("=" * 70)
    print("""
Synchronous vs. Batch:
  Synchronous: each call blocks — latency adds up linearly across tickets
  Batch: all requests submitted at once, processed in parallel at Anthropic's pace
  Cost: batch = 50% of synchronous price for the same tokens
  Tradeoff: batch has no latency SLA (up to 24 hours) — never use for real-time UX

custom_id:
  Results arrive out of order in the batch results stream
  Without custom_id there is no way to know which result belongs to which ticket
  Always set custom_id = your document's primary key

Multi-turn tool calling limitation:
  Each batch request is one turn: one user message → one assistant response
  If your workflow needs: call tool → get result → continue reasoning,
  that is TWO turns — you cannot do it in one batch request
  Solution: run batch 1, collect tool results, submit batch 2 with results injected

Multi-instance review:
  The review batch uses a FRESH context window per ticket
  The reviewer has no memory of generating the classification
  This breaks the self-anchoring bias that causes self-review to miss errors
  Pattern: first batch classifies; second batch reviews using output of first
""")


# ---------------------------------------------------------------------------
# REFLECTION QUESTIONS (answer in learnings.md)
# ---------------------------------------------------------------------------

REFLECTION = """
REFLECTION QUESTIONS — answer in learnings.md
==============================================

1. A user submits a support ticket and expects a response within 30 seconds.
   Synchronous or Batch API?
   -> synchronous

2. You need to analyze 10,000 contracts overnight for legal review.
   Synchronous or Batch API?
   -> api batch

3. Why can't you do multi-turn tool calling in a single batch request?
because batch requests only have one turn and cannot be interrupted by tool calls in between

4. What is `custom_id` and why is it important in batch workflows?
it is the only possibility to route back the results to the initial request input


5. Why does a model reviewing its own output produce fewer corrections
   than an independent review instance?
   because it is self-biased towards the implementation it did before 
"""


if __name__ == "__main__":
    # Uncomment to run the live workflow (uses API credits, batch may take minutes):
    # run_workflow()

    print(REFLECTION)
    print(
        "\nKey decision rule:\n"
        "  User waiting (< 30s) → synchronous\n"
        "  Latency-tolerant, high volume, cost matters → Batch API\n"
        "\nBatch constraint to remember:\n"
        "  One batch request = one turn. No multi-turn tool calling within a batch."
    )
