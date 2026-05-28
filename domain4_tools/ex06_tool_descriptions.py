"""
Domain 4 Exercise 6: Tool Descriptions & Routing
==================================================
CCA-F Topic: Tool Design & MCP Integration

Key concepts:
  - Tool descriptions are the PRIMARY routing mechanism — Claude reads
    the description to decide WHICH tool to call, not just how to call it.
  - What makes a good description: purpose, input formats, constraints,
    explicit boundaries vs. similar tools (the "I am NOT for X" clause).
  - Misrouting fix hierarchy:
      1. Improve the tool description  ← always try this first
      2. NOT few-shot examples         ← wrong lever for routing
      3. NOT routing classifiers       ← adds complexity, wrong problem
  - Sweet spot: 4–5 tools per agent. Reliability degrades at 10+, breaks at 18+.

THE EXERCISE:
  Part A — Bad descriptions: 3 tools with vague descriptions.
    Run the same 6 test queries and count misroutes.

  Part B — Fixed descriptions: same 3 tools, improved descriptions.
    Run the same queries and observe routing improve.

  Part C — Tool count scaling: add 7 more dummy tools (10 total).
    Run the same queries and observe degraded routing.

Run: python ex06_tool_descriptions.py
"""

import anthropic
import json

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Test queries — each has a clearly intended target tool
# ---------------------------------------------------------------------------
TEST_QUERIES = [
    # (query, intended_tool)
    ("Find all customer records from last month",         "search_database"),
    ("What is the current stock price of Apple?",        "search_web"),
    ("Show me orders placed between Jan 1 and Feb 28",   "search_database"),
    ("Who won the 2024 US election?",                    "search_web"),
    ("How many users signed up this week?",              "search_database"),
    ("What is the weather in Berlin right now?",         "search_web"),
]

# ---------------------------------------------------------------------------
# PART A — BAD tool descriptions (vague, overlapping)
# ---------------------------------------------------------------------------

TOOLS_BAD = [
    {
        "name": "search_database",
        "description": "Search for information.",  # vague — "information" could be anything
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_web",
        "description": "Search for information online.",  # still vague — "online" is underspecified
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_user_profile",
        "description": "Get user data.",  # no boundary vs search_database
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "The user ID"}
            },
            "required": ["user_id"]
        }
    },
]

# ---------------------------------------------------------------------------
# PART B — FIXED tool descriptions (specific, bounded, differentiated)
# ---------------------------------------------------------------------------

TOOLS_FIXED = [
    # {   "name": "create_new_order_in_database",
    #     "description": (
    #         "Create a new order entry for the internal database which stores order in the following format: "
    #         "id: Long, orderedAt: LocalDate, .. "
    #         "Use this when the user wants to do an order"
    #         "Input: A SQL-like creation query with all required fields"
    #         "Do NOT use this for other entites than orders or retrieval queries"
    #     ),
    #     "input_schema": {
    #         "type": "object",
    #         "properties": {
    #             "query": {

    #                 "type": "OrderDto", 
    #                 "description": (
    #                     ""
    #                 )
    #             }
    #         },
    #         "required": ["query"]     
    #         }
    #  },
    {
        "name": "search_database",
        "description": (
            "Query the internal company database for structured business records: "
            "customers, orders, signups, revenue, and usage metrics. "
            "Use this when the question involves our OWN data — e.g., 'how many users signed up', "
            "'show orders from last month', 'find customer records'. "
            "Input: a natural-language query or SQL-like filter expression. "
            "Do NOT use this for real-time external information (stock prices, news, weather) — "
            "use search_web for that."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural-language query or filter, e.g. "
                        "'customers who signed up in January' or 'orders > $500 last week'"
                    )
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_web",
        "description": (
            "Search the public internet for real-time or general-knowledge information: "
            "current events, stock prices, weather, sports results, public company info, "
            "or any question whose answer lives outside our internal database. "
            "Use this when the answer requires up-to-date external data. "
            "Do NOT use this to query our internal customer or order records — "
            "use search_database for that."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search terms or a question, e.g. 'AAPL stock price today'"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_user_profile",
        "description": (
            "Retrieve a SINGLE user's full profile by their exact user ID. "
            "Returns account details, preferences, and subscription tier for that specific user. "
            "Use this ONLY when you have a specific user_id and need their profile data. "
            "Do NOT use this to search across multiple users or filter by date — "
            "use search_database for aggregate or filtered user queries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The exact user ID string, e.g. 'usr_8a3f92'"
                }
            },
            "required": ["user_id"]
        }
    },
]

# ---------------------------------------------------------------------------
# PART C — 10 tools (same 3 fixed + 7 dummy tools with reasonable descriptions)
# ---------------------------------------------------------------------------

DUMMY_TOOLS = [
    {
        "name": "send_email",
        "description": "Send an email to one or more recipients. Use only when the user explicitly asks to send an email.",
        "input_schema": {"type": "object", "properties": {"to": {"type": "string"}, "body": {"type": "string"}}, "required": ["to", "body"]}
    },
    {
        "name": "create_ticket",
        "description": "Create a support or engineering ticket in the issue tracker. Use when the user asks to log a bug or task.",
        "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "description": {"type": "string"}}, "required": ["title"]}
    },
    {
        "name": "run_report",
        "description": "Execute a pre-built business intelligence report by report name. Use only for named reports like 'weekly_revenue' or 'churn_analysis'.",
        "input_schema": {"type": "object", "properties": {"report_name": {"type": "string"}}, "required": ["report_name"]}
    },
    {
        "name": "translate_text",
        "description": "Translate text from one language to another. Use when the user explicitly asks for translation.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}, "target_language": {"type": "string"}}, "required": ["text", "target_language"]}
    },
    {
        "name": "summarize_document",
        "description": "Summarize a long document given its document ID. Use when the user asks to summarize a stored document.",
        "input_schema": {"type": "object", "properties": {"document_id": {"type": "string"}}, "required": ["document_id"]}
    },
    {
        "name": "schedule_meeting",
        "description": "Schedule a calendar meeting with specified attendees. Use only when the user asks to book or schedule a meeting.",
        "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "attendees": {"type": "array", "items": {"type": "string"}}}, "required": ["title"]}
    },
    {
        "name": "get_system_status",
        "description": "Check the health and uptime status of internal services. Use when the user asks about system health, outages, or service status.",
        "input_schema": {"type": "object", "properties": {"service_name": {"type": "string"}}, "required": []}
    },
]

TOOLS_10 = TOOLS_FIXED + DUMMY_TOOLS

# ---------------------------------------------------------------------------
# Helper: run one query and return which tool Claude chose
# ---------------------------------------------------------------------------

def get_tool_choice(query: str, tools: list) -> str:
    """Send a query and return the name of the tool Claude chose, or 'no_tool'."""
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=200,
        tools=tools,
        tool_choice={"type": "auto"},
        messages=[{"role": "user", "content": query}]
    )

    for block in response.content:
        if block.type == "tool_use":
            return block.name

    return "no_tool"


# ---------------------------------------------------------------------------
# Helper: run all test queries and print a routing table
# ---------------------------------------------------------------------------

def run_routing_test(label: str, tools: list):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  ({len(tools)} tools)")
    print(f"{'='*60}")
    print(f"{'Query':<50} {'Intended':<22} {'Actual':<22} {'OK?'}")
    print("-" * 100)

    correct = 0
    for query, intended in TEST_QUERIES:
        actual = get_tool_choice(query, tools)
        ok = "YES" if actual == intended else "NO  <-- MISROUTE"
        if actual == intended:
            correct += 1
        display_query = query if len(query) <= 48 else query[:45] + "..."
        print(f"{display_query:<50} {intended:<22} {actual:<22} {ok}")

    print(f"\nRouting accuracy: {correct}/{len(TEST_QUERIES)}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Exercise 6: Tool Descriptions & Routing")
    print("=========================================")
    print("Choose which part to run:")
    print("  A   — Bad descriptions (baseline, expect misroutes)")
    print("  B   — Fixed descriptions (improved routing)")
    print("  C   — 10 tools (observe degradation vs Part B)")
    print("  all — Run A, B, C in sequence (best for comparison)")

    choice = input("\nEnter choice [A/B/C/all]: ").strip().upper()

    if choice in ("A", "ALL"):
        run_routing_test("PART A: BAD descriptions", TOOLS_BAD)

    if choice in ("B", "ALL"):
        run_routing_test("PART B: FIXED descriptions", TOOLS_FIXED)

    if choice in ("C", "ALL"):
        run_routing_test("PART C: 10 tools (fixed 3 + 7 dummy)", TOOLS_10)

    if choice not in ("A", "B", "C", "ALL"):
        print("Unknown choice.")

    print("\n" + "="*60)
    print("REFLECTION QUESTIONS (answer in learnings.md):")
    print("="*60)
    print("""
1. You have tools `search_documents` and `search_web`. Claude keeps
   calling the wrong one. What is the fix?

2. Why is adding few-shot examples NOT the right way to fix misrouting?

3. What specific information in a tool description most reliably steers
   routing?

4. At what tool count does reliability start to degrade, and why?

5. A PM suggests building a routing classifier in front of the tools.
   What's wrong with this?
""")
