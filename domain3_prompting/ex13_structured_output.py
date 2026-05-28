"""
Domain 3 Exercise 13: Structured Output via tool_use & JSON Schemas
CCA-F Topic: Prompt Engineering & Structured Output

KEY CONCEPTS
============
1. tool_use forces structured output even when no real tool exists —
   tool_choice={"type":"tool","name":"..."} guarantees a tool_use block response
   Example: 
   tools=[{
    "name": "extract_invoice",
    "description": "Extract invoice details"
    # ← There's no actual function being called
    # It's just a schema container
}]

# Claude calls: extract_invoice(invoice_number="INV-2024-001", ...)
# You DON'T run a function
# You just take the tool_use.input directly as your structured output

2. JSON schema prevents SYNTAX errors (wrong types, missing required fields) —
   it does NOT prevent SEMANTIC errors (fabrication, wrong values, hallucinated data)
3. Schema design:
   - optional/nullable fields (anyOf string|null) let Claude signal "not present"
   - "unclear" enum value lets Claude signal ambiguity without fabricating
   - "other" + freeform note field handles open-ended extensibility
4. Validation-retry loop: send original doc + failed extraction + specific errors
   — works for format/logic errors, NOT for absent data (semantic limit)
5. A retry loop that keeps failing on the same field means the schema is wrong,
   not that Claude needs more retries — fix the schema, not the loop count

EXERCISE STRUCTURE
==================
Section 1 — Strict schema (all fields required): observe fabrication on missing data
Section 2 — Permissive schema (nullable + "unclear" + "other"): fix fabrication risk
Section 3 — Validation-retry loop: catch format errors; show limits on absent data
"""

import anthropic
import json
import re

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Sample invoice documents (some complete, some with missing/ambiguous fields)
# ---------------------------------------------------------------------------

DOCUMENTS = [
    {
        "id": "doc_complete",
        "text": """INVOICE #INV-2024-001
Date: March 15, 2024
Customer: Acme Corporation
Amount: $4,250.00
Category: Software subscription
Payment terms: Net 30
Status: Unpaid""",
    },
    {
        "id": "doc_missing_customer",
        "text": """INVOICE #INV-2024-002
Date: April 3, 2024
Amount: $1,100.00
Category: Consulting services
Payment terms: Net 15
Status: Paid""",
        # No customer name — triggers fabrication in strict schema
    },
    {
        "id": "doc_ambiguous_status",
        "text": """INVOICE #INV-2024-003
Date: February 28, 2024
Customer: Beta LLC
Amount: $7,800.00
Category: Hardware
Note: Payment pending review by finance team — awaiting approval.""",
        # Status is ambiguous: is it paid, unpaid, or something else?
    },
    {
        "id": "doc_extensible_category",
        "text": """INVOICE #INV-2024-004
Date: May 10, 2024
Customer: Gamma Inc.
Amount: $550.00
Category: On-site equipment calibration visit
Status: Cancelled""",
        # Category doesn't fit standard enum values — tests "other" + note
    },
]


# ---------------------------------------------------------------------------
# SECTION 1: Strict schema — all fields required
# Observe: Claude fabricates customer_name for doc_missing_customer
#          Claude picks an enum value for ambiguous status (doc_ambiguous_status)
# ---------------------------------------------------------------------------

STRICT_TOOL = {
    "name": "extract_invoice",
    "description": "Extract invoice details from the document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "invoice_number": {"type": "string", "description": "Invoice identifier, e.g. INV-2024-001"},
            "date": {"type": "string", "description": "Invoice date as written"},
            "customer_name": {"type": "string", "description": "Name of the customer"},
            "amount_usd": {"type": "number", "description": "Invoice amount in USD"},
            "status": {
                "type": "string",
                "enum": ["paid", "unpaid", "cancelled"],
                "description": "Payment status",
            },
        },
        "required": ["invoice_number", "date", "customer_name", "amount_usd", "status"],
    },
}


def extract_strict(doc: dict) -> dict:
    """Section 1: extract with strict schema — all fields required."""
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        tools=[STRICT_TOOL],
        tool_choice={"type": "tool", "name": "extract_invoice"},
        messages=[
            {
                "role": "user",
                "content": f"Extract invoice details from this document:\n\n{doc['text']}",
            }
        ],
    )
    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    return tool_use_block.input


# ---------------------------------------------------------------------------
# SECTION 2: Permissive schema — nullable fields + "unclear" enum + "other" category
# Fix: Claude can now return null for absent fields and "unclear" for ambiguous status
# ---------------------------------------------------------------------------

PERMISSIVE_TOOL = {
    "name": "extract_invoice",
    "description": (
        "Extract invoice details from the document. "
        "Use null for any field not explicitly stated. "
        "Use 'unclear' for status when the document is ambiguous. "
        "Use category='other' and fill category_note when the type doesn't fit standard categories."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "invoice_number": {
                "type": "string",
                "description": "Invoice identifier",
            },
            "date": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Invoice date as written, or null if not present",
            },
            "customer_name": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Customer name, or null if not mentioned",
            },
            "amount_usd": {
                "anyOf": [{"type": "number"}, {"type": "null"}],
                "description": "Amount in USD, or null if not present",
            },
            "status": {
                "type": "string",
                "enum": ["paid", "unpaid", "cancelled", "unclear"],
                "description": "Payment status. Use 'unclear' when the document is ambiguous.",
            },
            "category": {
                "type": "string",
                "enum": ["product", "service", "subscription", "other"],
                "description": "Invoice category. Use 'other' when none of the standard values fit.",
            },
            "category_note": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Required when category='other': describe the actual category in a few words.",
            },
        },
        "required": ["invoice_number", "status", "category"],
    },
}


def extract_permissive(doc: dict) -> dict:
    """Section 2: extract with permissive schema — nullable + 'unclear' + 'other'."""
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        tools=[PERMISSIVE_TOOL],
        tool_choice={"type": "tool", "name": "extract_invoice"},
        messages=[
            {
                "role": "user",
                "content": f"Extract invoice details from this document:\n\n{doc['text']}",
            }
        ],
    )
    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    return tool_use_block.input


# ---------------------------------------------------------------------------
# SECTION 3: Validation-retry loop
#
# Custom validations that JSON schema CANNOT enforce:
#   - invoice_number must match pattern INV-YYYY-NNN
#   - amount_usd must be positive
#   - category='other' requires category_note to be non-null
#
# Retry strategy: include original doc + failed extraction + specific errors
# Demonstrate the LIMIT: if a field is absent from the doc, retries won't add data
# ---------------------------------------------------------------------------

INV_NUMBER_PATTERN = re.compile(r"^INV-\d{4}-\d{3}$")


def validate_extraction(extracted: dict) -> list[str]:
    """Return a list of validation error strings. Empty list = valid."""
    errors = []

    inv_num = extracted.get("invoice_number", "")
    if not INV_NUMBER_PATTERN.match(inv_num):
        errors.append(
            f"invoice_number '{inv_num}' does not match required format INV-YYYY-NNN"
        )

    amount = extracted.get("amount_usd")
    if amount is not None and amount <= 0:
        errors.append(f"amount_usd must be positive, got {amount}")

    if extracted.get("category") == "other" and not extracted.get("category_note"):
        errors.append("category_note is required when category is 'other'")

    return errors


def extract_with_retry(doc: dict, max_retries: int = 2) -> dict:
    """
    Section 3: extract + validate, retry with errors if invalid.
    Sends original doc + failed output + specific errors on each retry.
    """
    messages = [
        {
            "role": "user",
            "content": f"Extract invoice details from this document:\n\n{doc['text']}",
        }
    ]

    for attempt in range(1, max_retries + 2):  # +2: first attempt + max_retries
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            tools=[PERMISSIVE_TOOL],
            tool_choice={"type": "tool", "name": "extract_invoice"},
            messages=messages,
        )

        tool_use_block = next(b for b in response.content if b.type == "tool_use")
        extracted = tool_use_block.input
        errors = validate_extraction(extracted)

        if not errors:
            return {
                "doc_id": doc["id"],
                "attempts": attempt,
                "result": extracted,
                "status": "valid",
            }

        if attempt > max_retries:
            return {
                "doc_id": doc["id"],
                "attempts": attempt,
                "result": extracted,
                "status": "failed_validation",
                "errors": errors,
            }

        # Build retry: append Claude's tool_use turn + a new user message with errors
        # Include the original doc + the failed extraction + the specific errors
        # This gives Claude everything it needs to correct format/logic errors
        messages.append({"role": "assistant", "content": response.content})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"The extraction has {len(errors)} validation error(s). "
                    f"Please re-extract from the original document and fix these issues:\n\n"
                    + "\n".join(f"- {e}" for e in errors)
                    + f"\n\nOriginal document for reference:\n{doc['text']}"
                ),
            }
        )

    # unreachable, but satisfies type checkers
    return {"doc_id": doc["id"], "attempts": max_retries + 1, "status": "failed_validation"}


# ---------------------------------------------------------------------------
# SECTION 4: Run all sections and compare
# ---------------------------------------------------------------------------


def run_comparison():
    print("=" * 70)
    print("STRUCTURED OUTPUT: Strict vs. Permissive vs. Validation-Retry")
    print("=" * 70)

    print("\n--- SECTION 1: Strict schema (all fields required) ---")
    print("Watch for fabrication on doc_missing_customer and wrong enum on doc_ambiguous_status\n")
    for doc in DOCUMENTS:
        result = extract_strict(doc)
        print(f"{doc['id']:30s} → {json.dumps(result)}")

    print("\n--- SECTION 2: Permissive schema (nullable + 'unclear' + 'other') ---")
    print("customer_name should be null; status should be 'unclear'; category 'other' + note\n")
    for doc in DOCUMENTS:
        result = extract_permissive(doc)
        print(f"{doc['id']:30s} → {json.dumps(result)}")

    print("\n--- SECTION 3: Validation-retry loop ---")
    # doc_complete should pass on first attempt
    # Manually corrupt one extraction to trigger a retry by inserting a bad invoice number
    print("Running retry loop on all documents (max 2 retries each)\n")
    for doc in DOCUMENTS:
        result = extract_with_retry(doc)
        print(
            f"{result['doc_id']:30s} → attempts={result['attempts']} "
            f"status={result['status']}"
        )
        if result.get("errors"):
            print(f"  validation errors: {result['errors']}")

    print("\n" + "=" * 70)
    print("WHAT TO OBSERVE")
    print("=" * 70)
    print("""
Section 1 — Strict schema:
  doc_missing_customer: customer_name is FABRICATED (Claude invents a name)
    → JSON schema cannot detect this — it's a semantic error, not a syntax error
  doc_ambiguous_status: Claude picks "unpaid" or similar even though it's unclear
    → Schema enforces a valid enum value but can't enforce honest uncertainty

Section 2 — Permissive schema:
  doc_missing_customer: customer_name = null (no fabrication)
  doc_ambiguous_status: status = "unclear" (honest signal)
  doc_extensible_category: category = "other", category_note describes the real type
    → These require EXPLICIT schema design choices; nullability doesn't happen by default

Section 3 — Validation-retry loop:
  Format errors (invoice_number pattern) CAN be fixed by retry — Claude sees
    the error message and the original document, so it can re-read and reformat
  Absent data (customer_name = null) will NEVER be fixed by retry — the info
    isn't in the document; retrying only makes Claude fabricate under pressure
  KEY INSIGHT: a loop that keeps failing on the same field means the schema
    needs an "unclear"/null escape hatch — not more retries
""")


# ---------------------------------------------------------------------------
# REFLECTION QUESTIONS (answer in learnings.md)
# ---------------------------------------------------------------------------

REFLECTION = """
REFLECTION QUESTIONS — answer in learnings.md
==============================================

1. Why use `tool_use` for structured output when there's no tool to call?

2. A JSON schema marks `customer_name` as required.
   The document doesn't mention the customer. What does Claude do?

3. What is the difference between a syntax error and a semantic error
   in structured output? Give one example of each.

4. A validation-retry loop keeps failing on the same field. What does this tell you?

5. When is a validation-retry loop the wrong solution?
"""


if __name__ == "__main__":
    # Uncomment to run the live comparison (uses API credits):
    # run_comparison()

    print(REFLECTION)
    print(
        "\nKey extraction outcomes to watch:\n"
        "  doc_missing_customer  → strict: fabricated name | permissive: null\n"
        "  doc_ambiguous_status  → strict: forced enum pick | permissive: 'unclear'\n"
        "  doc_extensible_category → permissive: category='other' + category_note"
    )
