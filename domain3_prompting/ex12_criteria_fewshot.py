"""
Domain 3 Exercise 12: Explicit Criteria & Few-Shot Prompting
CCA-F Topic: Prompt Engineering & Structured Output

KEY CONCEPTS
============
1. Vague instructions ("be conservative") produce inconsistent results at scale
2. Specific categorical criteria pin behavior: "flag ONLY when X, never when Y"
3. High false-positive rates in ONE category destroy trust in ALL categories
4. Few-shot examples: deploy AFTER detailed instructions still produce inconsistency
5. Each example must show the REASONING, not just the answer

EXERCISE STRUCTURE
==================
Version 1 — vague instruction:  "only flag high-confidence issues"
Version 2 — explicit criteria:   specific categorical rules per issue type
Version 3 — add few-shot examples showing reasoning
"""

import anthropic
import json

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Sample code snippets to review (same set used across all 3 versions)
# ---------------------------------------------------------------------------

CODE_SNIPPETS = [
    {
        "id": "snippet_1",
        "language": "python",
        "code": """
def get_user(user_id):
    # Fetch user from database
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)
""",
        "comment": "Fetch user from database",
    },
    {
        "id": "snippet_2",
        "language": "python",
        "code": """
def calculate_discount(price, pct):
    # Apply percentage discount to price
    return price * (1 - pct / 100)
""",
        "comment": "Apply percentage discount to price",
    },
    {
        "id": "snippet_3",
        "language": "python",
        "code": """
def read_file(path):
    # Opens and returns file contents from the uploads directory
    with open(path, "r") as f:
        return f.read()
""",
        "comment": "Opens and returns file contents from the uploads directory",
    },
    {
        "id": "snippet_4",
        "language": "python",
        "code": """
def is_admin(user):
    # Returns True if user has admin access
    return user.get("role") == "admin" or user.get("is_superuser")
""",
        "comment": "Returns True if user has admin access",
    },
    {
        "id": "snippet_5",
        "language": "python",
        "code": """
def send_email(to, subject, body):
    # Sends email to user
    smtp.sendmail(FROM_ADDR, to, f"Subject: {subject}\n\n{body}")
""",
        "comment": "Sends email to user",
    },
]


# ---------------------------------------------------------------------------
# SECTION 1: Version 1 — VAGUE instruction
# ---------------------------------------------------------------------------

VAGUE_SYSTEM = """You are a code review assistant.
Review code comments for accuracy. Only flag high-confidence issues.
Be conservative — only report issues you are very sure about."""


def review_with_vague_instruction(snippet: dict) -> dict:
    """Version 1: vague instruction — observe inconsistent flagging."""
    prompt = f"""Review this code comment for accuracy.

Comment: "{snippet['comment']}"

Code:
```{snippet['language']}
{snippet['code']}
```

Should this comment be flagged as misleading? Answer with:
- flagged: true or false
- reason: one sentence
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=VAGUE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return {"id": snippet["id"], "version": "vague", "response": response.content[0].text}


# ---------------------------------------------------------------------------
# SECTION 2: Version 2 — EXPLICIT categorical criteria
# ---------------------------------------------------------------------------

EXPLICIT_SYSTEM = """You are a code review assistant that flags misleading comments.

Flag a comment as misleading ONLY when it meets one of these specific criteria:

CRITERION A — Contradicts actual behavior:
  The comment describes what the function does, but the code does something
  different or opposite.
  Example: comment says "returns True if admin" but code returns True for ALL users.

CRITERION B — Omits a critical security constraint:
  The comment implies safety (e.g., "from the uploads directory") but the code
  has no path validation — any path can be passed.

CRITERION C — Describes a side effect that isn't present:
  The comment claims the function saves, sends, or writes something, but the code
  only reads or computes.

DO NOT flag:
- Comments that are incomplete but not wrong
- Comments that simplify without misleading
- Style issues (capitalization, punctuation)

Output ONLY JSON: {"flagged": true/false, "criterion": "A/B/C/none", "reason": "one sentence"}"""


def review_with_explicit_criteria(snippet: dict) -> dict:
    """Version 2: explicit categorical criteria — observe consistent flagging."""
    prompt = f"""Review this code comment.

Comment: "{snippet['comment']}"

Code:
```{snippet['language']}
{snippet['code']}
```
"""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=EXPLICIT_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return {"id": snippet["id"], "version": "explicit", "response": response.content[0].text}


# ---------------------------------------------------------------------------
# SECTION 3: Version 3 — Explicit criteria + FEW-SHOT EXAMPLES
# ---------------------------------------------------------------------------

# Few-shot examples each show:
# 1. The comment and code
# 2. The REASONING process (which criterion, why it applies or doesn't)
# 3. The final decision
# This teaches the boundary, not just the answer.

FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": """Review this code comment.

Comment: "Validates the email address"

Code:
```python
def check_email(email):
    return "@" in email
```""",
    },
    {
        "role": "assistant",
        "content": """{"flagged": false, "criterion": "none", "reason": "The comment says 'validates email' and the code does check for '@' — this is a simplified but not wrong description of lightweight validation."}

Reasoning: I checked each criterion. A) The comment doesn't contradict the behavior — it does check the email. B) No security constraint is implied. C) No side effect is claimed. The comment is incomplete (real validation is more complex) but not misleading. Not flagged.""",
    },
    {
        "role": "user",
        "content": """Review this code comment.

Comment: "Returns user data from the secure internal API"

Code:
```python
def get_user_data(user_id):
    url = f"https://api.example.com/users/{user_id}"
    return requests.get(url).json()
```""",
    },
    {
        "role": "assistant",
        "content": """{"flagged": true, "criterion": "A", "reason": "The comment claims 'secure internal API' but the code uses a public HTTPS endpoint with no authentication headers — the 'secure' and 'internal' claims contradict what the code actually does."}

Reasoning: Criterion A applies — the comment describes an attribute (secure, internal) that the code does not exhibit. The endpoint is external and there is no auth. This is a direct contradiction between comment and code behavior. Flagged.""",
    },
    {
        "role": "user",
        "content": """Review this code comment.

Comment: "Saves the report to disk"

Code:
```python
def generate_report(data):
    report = {"summary": data["total"], "items": data["rows"]}
    return report
```""",
    },
    {
        "role": "assistant",
        "content": """{"flagged": true, "criterion": "C", "reason": "The comment claims the function saves to disk but the code only builds and returns a dict — no file write occurs anywhere."}

Reasoning: Criterion C applies — the comment describes a side effect (saving to disk) that is completely absent from the code. The function only constructs and returns data. A caller relying on this comment would assume persistence that doesn't exist. Flagged.""",
    },
]


def review_with_few_shot(snippet: dict) -> dict:
    """Version 3: explicit criteria + few-shot examples showing reasoning."""
    messages = FEW_SHOT_EXAMPLES + [
        {
            "role": "user",
            "content": f"""Review this code comment.

Comment: "{snippet['comment']}"

Code:
```{snippet['language']}
{snippet['code']}
```""",
        }
    ]

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=EXPLICIT_SYSTEM,
        messages=messages,
    )
    return {"id": snippet["id"], "version": "few_shot", "response": response.content[0].text}


# ---------------------------------------------------------------------------
# SECTION 4: Run all 3 versions and compare
# ---------------------------------------------------------------------------

def run_comparison():
    print("=" * 70)
    print("CODE REVIEW COMPARISON: Vague vs. Explicit vs. Few-Shot")
    print("=" * 70)

    for snippet in CODE_SNIPPETS:
        print(f"\n--- {snippet['id']} ---")
        print(f"Comment : \"{snippet['comment']}\"")
        print(f"Code    : {snippet['code'].strip()[:80]}...")

        v1 = review_with_vague_instruction(snippet)
        v2 = review_with_explicit_criteria(snippet)
        v3 = review_with_few_shot(snippet)

        print(f"\nV1 (vague)    : {v1['response'][:120]}")
        print(f"V2 (explicit) : {v2['response'][:120]}")
        print(f"V3 (few-shot) : {v3['response'][:120]}")

    print("\n" + "=" * 70)
    print("WHAT TO OBSERVE")
    print("=" * 70)
    print("""
snippet_1 (SQL injection):
  Expected: FLAGGED — comment says "fetch user" but omits that it's vulnerable
  V1: may or may not flag depending on interpretation of "conservative"
  V2/V3: should flag consistently under Criterion B (security constraint omitted)

snippet_2 (discount):
  Expected: NOT flagged — comment accurately describes what the code does
  V1: may over-flag ("pct" naming is unclear — is this a false positive?)
  V2/V3: should NOT flag — comment is accurate, just brief

snippet_3 (file read):
  Expected: FLAGGED — "from the uploads directory" implies path restriction,
  but code accepts any path (path traversal risk — Criterion B)
  V1: inconsistent — "uploads directory" sounds specific but may not trigger flag
  V2/V3: should flag consistently

snippet_4 (is_admin):
  Expected: NOT flagged — comment accurately describes the OR logic
  V1: may flag because "or is_superuser" is not mentioned
  V2/V3: should NOT flag — both conditions grant admin; comment is accurate

snippet_5 (send_email):
  Expected: NOT flagged — comment matches what the function does
  V1: might flag for style or missing detail
  V2/V3: should NOT flag — no criterion is triggered

KEY INSIGHT:
  V1 false positives (flagging snippet_2 or snippet_4) destroy trust.
  If reviewers see false flags on accurate code, they stop trusting ALL flags —
  including the real ones (snippet_1, snippet_3).
  Explicit criteria in V2 cut false positives.
  Few-shot in V3 stabilize judgment on ambiguous cases (snippet_4's OR logic).
""")


# ---------------------------------------------------------------------------
# REFLECTION QUESTIONS (answer in learnings.md)
# ---------------------------------------------------------------------------

REFLECTION = """
REFLECTION QUESTIONS — answer in learnings.md
==============================================

1. Why is "only flag high-confidence issues" a bad instruction?

2. What makes a few-shot example useful vs. just padding?
   What must it demonstrate?

3. When should you NOT use few-shot examples for tool routing?

4. A model has a 15% false-positive rate on one category but 2% overall.
   Why does the 15% matter even if the average looks fine?

5. Write a specific categorical criterion for "flag a comment as misleading."
   What does it include?
"""


if __name__ == "__main__":
    # Uncomment to run the live comparison (uses API credits):
    # run_comparison()

    print(REFLECTION)
    print("\nExpected flags: snippet_1 (SQL injection), snippet_3 (path traversal)")
    print("Expected clean: snippet_2 (discount), snippet_4 (is_admin), snippet_5 (email)")
