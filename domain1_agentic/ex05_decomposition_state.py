"""
Domain 1 Exercise 5: Task Decomposition & Session State
=========================================================
CCA-F Topic: Agentic Architecture & Orchestration

Key concepts:
  - Fixed sequential pipeline: predetermined steps, each building on the last
  - Dynamic adaptive decomposition: Claude decides what to do next based on results
  - Attention dilution: sending too many items in one prompt → shallow analysis
  - Two-pass pattern: local analysis passes + separate integration pass
  - In-context state: lives in the messages list (lost when session ends)
  - External state: lives in a database/file (survives across sessions)
  - Session resumption: --resume, fork_session, or fresh start + summary injection

THE EXERCISE:
  Analyze 10 code "files" (simulated as strings) for security issues.

  Version 1 — Naive: send all 10 in one prompt.
    Observe: Claude gives a generic, shallow analysis. Specific issues
    in middle files get missed or glossed over. This is attention dilution.

  Version 2 — Two-pass: send each file individually, collect findings,
    then send all findings to a final integration call that synthesizes.
    Observe: per-file analysis is specific and catches issues. Integration
    call produces a prioritized report without re-reading 10 files.

Run: python ex05_decomposition_state.py
"""

import anthropic
import json

client = anthropic.Anthropic()

# --- Simulated codebase ---
# 10 "files", each with a different security issue embedded.
# Files 4–7 (the "middle") contain the most critical issues.
# Attention dilution causes these to be under-analyzed in Version 1.

CODE_FILES = {
    "auth/login.py": """
def login(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    result = db.execute(query)  # SQL INJECTION: user input directly in query
    return result
""",
    "auth/tokens.py": """
SECRET_KEY = "hardcoded_secret_123"  # HARDCODED SECRET in source code

def generate_token(user_id):
    return jwt.encode({"user_id": user_id}, SECRET_KEY, algorithm="HS256")
""",
    "api/payments.py": """
def process_payment(amount, card_number):
    log.info(f"Processing payment: card={card_number}, amount={amount}")  # PCI: logging card number
    return stripe.charge(card_number, amount)
""",
    "api/upload.py": """
def handle_upload(filename, content):
    # No file type validation — allows .exe, .sh, arbitrary uploads
    path = f"/uploads/{filename}"
    with open(path, "wb") as f:
        f.write(content)
    return path
""",
    "api/admin.py": """
def get_user_data(user_id):
    # No authorization check — any authenticated user can access any user's data
    return db.query("SELECT * FROM users WHERE id=?", user_id)
""",
    "utils/crypto.py": """
import md5  # WEAK HASH: MD5 is broken for passwords

def hash_password(password):
    return md5.new(password).hexdigest()
""",
    "utils/serialize.py": """
import pickle

def load_session(session_data):
    return pickle.loads(session_data)  # INSECURE DESERIALIZATION: pickle with untrusted input
""",
    "web/templates.py": """
def render_profile(username):
    # No escaping — XSS vulnerability
    html = f"<h1>Welcome, {username}!</h1>"
    return html
""",
    "config/settings.py": """
DEBUG = True          # DEBUG mode left on in production config
ALLOWED_HOSTS = ["*"] # Overly permissive host configuration
""",
    "tests/test_auth.py": """
def test_login():
    # Test passes even when SQL injection succeeds — test doesn't validate correctly
    result = login("admin'--", "anything")
    assert result is not None  # This passes with injection, masking the bug
""",
}

ANALYSIS_PROMPT = """You are a security code reviewer. Analyze the code for security vulnerabilities.
For each issue found, identify:
1. The vulnerability type (e.g., SQL injection, XSS, etc.)
2. The exact line or pattern that is vulnerable
3. The severity (Critical / High / Medium / Low)
4. A one-sentence fix recommendation

Be specific — name the exact variable, function, or line involved."""


# =============================================================================
# VERSION 1: Naive — all 10 files in one prompt (attention dilution demo)
# =============================================================================

def version1_naive():
    """
    Send all 10 files in a single prompt.
    Watch how the analysis gets shallow for middle files (files 4–7).
    """
    print("\n" + "="*60)
    print("VERSION 1: NAIVE (all 10 files in one prompt)")
    print("="*60)

    # Concatenate all files into one giant prompt
    all_code = ""
    for filename, code in CODE_FILES.items():
        all_code += f"\n\n### File: {filename}\n```python{code}```"

    prompt = f"""{ANALYSIS_PROMPT}

Here are 10 files to review:{all_code}

Provide a complete security review of ALL 10 files."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    print("\n--- Claude's response (naive, all files at once) ---")
    print(response.content[0].text)
    print(f"\n[Token usage: input={response.usage.input_tokens}, output={response.usage.output_tokens}]")
    print("\nNOTE: Check if files 4–7 (api/admin.py, utils/crypto.py, etc.) got")
    print("      specific analysis or were lumped together / mentioned briefly.")


# =============================================================================
# VERSION 2: Two-pass — local analysis per file + final integration call
# =============================================================================

def version2_two_pass():
    """
    Pass 1: Analyze each file individually. Collect structured findings.
    Pass 2: Send all findings to a synthesis call that builds a priority report.

    This avoids attention dilution because each local pass focuses on ONE file.
    The integration pass never re-reads raw code — only structured findings.
    """
    print("\n" + "="*60)
    print("VERSION 2: TWO-PASS (local analysis + integration)")
    print("="*60)

    # --- PASS 1: Local analysis — one API call per file ---
    all_findings = []

    print("\n--- Pass 1: Per-file analysis ---")
    for filename, code in CODE_FILES.items():
        prompt = f"""{ANALYSIS_PROMPT}

File: {filename}
```python{code}```

List ONLY the issues found in THIS file. Be specific."""

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        finding = {
            "file": filename,
            "analysis": response.content[0].text,
            "input_tokens": response.usage.input_tokens,
        }
        all_findings.append(finding)

        # Show a preview of each per-file finding
        preview = response.content[0].text[:120].replace("\n", " ")
        print(f"  {filename}: {preview}...")

    # --- PASS 2: Integration — synthesize all findings ---
    print("\n--- Pass 2: Integration / synthesis ---")

    findings_summary = ""
    for f in all_findings:
        findings_summary += f"\n\n### {f['file']}\n{f['analysis']}"

    integration_prompt = f"""You have received per-file security findings from a code review of a 10-file codebase.

Your task: synthesize these findings into an executive security report with:
1. Top 3 critical issues that must be fixed immediately (with file + issue name)
2. Patterns: are there systemic problems (e.g., "no input validation anywhere")?
3. Recommended fix order (most impactful first)

Do NOT re-analyze the code. Work only from the findings below.

FINDINGS:
{findings_summary}"""

    integration_response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": integration_prompt}]
    )

    print("\n--- Integration report ---")
    print(integration_response.content[0].text)

    total_pass1_tokens = sum(f["input_tokens"] for f in all_findings)
    print(f"\n[Pass 1 total input tokens: {total_pass1_tokens}]")
    print(f"[Pass 2 input tokens: {integration_response.usage.input_tokens}]")
    print(f"[Pass 2 output tokens: {integration_response.usage.output_tokens}]")


# =============================================================================
# STATE DEMO: in-context vs external state
# =============================================================================

def state_demo():
    """
    Demonstrates the difference between in-context and external state.

    In-context state:  the `messages` list. Survives only while the list exists.
    External state:    a file/database written during the session.
                       Survives process restarts and can be loaded in a new session.

    Session resumption patterns (Claude Code context — not shown in code here):
      --resume         : reload a previous conversation from its ID
      fork_session     : branch a conversation for a different direction
      summary injection: start fresh but inject a compact summary of prior work
                         → use when prior context is too long or you want a clean start
    """
    print("\n" + "="*60)
    print("STATE DEMO: in-context vs external state")
    print("="*60)

    # --- In-context state: the messages list ---
    messages = []

    messages.append({
        "role": "user",
        "content": "Remember: the project is called ATLAS and has 3 microservices."
    })
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=100,
        messages=messages
    )
    messages.append({"role": "assistant", "content": response.content[0].text})

    messages.append({
        "role": "user",
        "content": "What is the project called and how many microservices does it have?"
    })
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=100,
        messages=messages
    )
    messages.append({"role": "assistant", "content": response.content[0].text})

    print("\nIn-context state (Claude remembers within the messages list):")
    print(f"  Claude says: {response.content[0].text.strip()}")
    print("  → If you clear `messages` or restart the process, this is gone.\n")

    # --- External state: write findings to a file ---
    # In a real agent, this would be a database. Here we use a JSON file.
    state_file = "/tmp/ex05_session_state.json"
    session_state = {
        "project": "ATLAS",
        "microservices": 3,
        "findings_count": len(CODE_FILES),
        "critical_issues": ["SQL injection in auth/login.py", "insecure deserialization in utils/serialize.py"],
    }
    with open(state_file, "w") as f:
        json.dump(session_state, f, indent=2)

    print("External state (written to file — survives process restart):")
    print(f"  Saved to: {state_file}")
    print(f"  Contents: {json.dumps(session_state, indent=4)}")

    # Simulate resuming: load state and inject as context
    with open(state_file) as f:
        loaded_state = json.load(f)

    summary_injection = f"""You are resuming work on the ATLAS project.
Prior session findings:
- Analyzed {loaded_state['findings_count']} files
- Critical issues found: {', '.join(loaded_state['critical_issues'])}
- Project has {loaded_state['microservices']} microservices

Continue from here."""

    resume_response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=150,
        messages=[{"role": "user", "content": summary_injection + "\n\nWhat were the critical issues found?"}]
    )

    print("\nAfter summary injection (fresh session, no conversation history):")
    print(f"  Claude says: {resume_response.content[0].text.strip()}")
    print("  → Claude knows the prior findings because we injected them as context,")
    print("    NOT because they were in the messages list.")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("Exercise 5: Task Decomposition & Session State")
    print("================================================")
    print("Choose which version to run:")
    print("  1 — Naive (all files in one prompt, attention dilution demo)")
    print("  2 — Two-pass (local analysis + integration, recommended pattern)")
    print("  3 — State demo (in-context vs external state + session resumption)")
    print("  all — Run all three in sequence")

    choice = input("\nEnter choice [1/2/3/all]: ").strip().lower()

    if choice in ("1", "all"):
        version1_naive()
    if choice in ("2", "all"):
        version2_two_pass()
    if choice in ("3", "all"):
        state_demo()

    if choice not in ("1", "2", "3", "all"):
        print("Unknown choice. Run with 1, 2, 3, or all.")

    print("\n" + "="*60)
    print("REFLECTION QUESTIONS (answer in learnings.md):")
    print("="*60)
    print("""
1. What is the attention dilution problem and how does the two-pass
   approach solve it?

2. When would you use `fork_session` instead of `--resume`?

3. What information should go in a "summary injection" when starting
   a fresh session?

4. What is the difference between fixed sequential and dynamic adaptive
   decomposition — when does each shine?

5. Where does session state live in the ex01 agentic loop, and what
   would you need to add to persist it across sessions?
""")
