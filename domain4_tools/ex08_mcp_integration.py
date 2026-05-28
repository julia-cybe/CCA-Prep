"""
Domain 4 Exercise 8: MCP Integration
=====================================
CCA-F Topic: Tool Design & MCP Integration

Key concepts:
  - MCP (Model Context Protocol): an open standard that lets Claude connect to
    external systems via a well-defined server interface. The server exposes
    capabilities; Claude consumes them through the host (Claude Code, API, etc.)

  - Two capability types exposed by MCP servers:
      tools     → functions Claude can CALL (write, side-effects possible)
      resources → read-only data Claude can READ (like context injection)

  - Two config scopes in Claude Code:
      project-level  → .mcp.json at the project root (version-controlled, shared)
      user-level     → ~/.claude.json under "mcpServers" key (personal, not shared)

  - Credential management:
      NEVER hardcode API keys in .mcp.json — it gets committed to version control.
      Use ${ENV_VAR} placeholders. Claude Code expands them at startup from the
      shell environment.

  - When to use community vs. custom MCP servers:
      community  → well-maintained, immediate value, no build cost
                   (filesystem, fetch, GitHub, Slack, Postgres…)
      custom     → proprietary APIs, internal systems, bespoke data formats,
                   or when community servers expose too much/too little surface

THE EXERCISE:
  Part A — MCP anatomy. Read and understand the config JSON structures.
    See what a project-level and a user-level config look like side-by-side.

  Part B — Scoping demo (simulated). A "new teammate" clones the repo.
    Which config does she see? Which does she NOT see? Why?

  Part C — Credential hygiene check.
    Compare a BAD config (key hardcoded) vs. a GOOD config (env-var reference).

  Part D — tools vs. resources distinction.
    Inspect the difference through example payloads and decide which to use
    for a given scenario.

  Part E — Community vs. custom decision tree.
    Work through 4 scenarios and decide: existing server or build custom?

Run: python ex08_mcp_integration.py
"""

import json
import os


# ---------------------------------------------------------------------------
# Shared pretty-printer
# ---------------------------------------------------------------------------

def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def show_json(label: str, obj: dict):
    print(f"\n--- {label} ---")
    print(json.dumps(obj, indent=2))


# ---------------------------------------------------------------------------
# PART A — MCP anatomy: config structures
# ---------------------------------------------------------------------------

# Project-level: committed to the repo, visible to every team member who clones it.
# Location: <project-root>/.mcp.json
PROJECT_MCP_JSON = {
    "mcpServers": {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp/project-data"],
            "description": "Read/write access to project data directory"
        },
        "fetch": {
            "command": "uvx",
            "args": ["mcp-server-fetch"],
            "description": "HTTP fetch tool for retrieving web content"
        },
        "internal-crm": {
            "command": "python",
            "args": ["-m", "crm_mcp_server"],
            "env": {
                "CRM_API_KEY": "${CRM_API_KEY}",      # <-- env-var reference, not the key itself
                "CRM_BASE_URL": "${CRM_BASE_URL}"
            },
            "description": "Custom MCP server wrapping our internal CRM API"
        }
    }
}

# User-level: personal config, NOT committed to version control.
# Location: ~/.claude.json  (under the "mcpServers" key)
# Anything here is only visible to THIS developer on THIS machine.
USER_CLAUDE_JSON_SNIPPET = {
    "mcpServers": {
        "personal-notes": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/julia/notes"],
            "description": "Julia's personal notes — not shared with the team"
        }
    }
}


def part_a_anatomy():
    section("PART A: MCP config anatomy")

    show_json("Project-level config  (.mcp.json — committed to repo)", PROJECT_MCP_JSON)
    show_json("User-level config snippet  (~/.claude.json — personal only)", USER_CLAUDE_JSON_SNIPPET)

    print("""
KEY OBSERVATIONS:
  1. Both use the same "mcpServers" key and server shape:
       { "command": ..., "args": [...], "env": {...} }

  2. Project-level config is version-controlled → every team member sees it
     when they clone the repo.

  3. User-level config lives outside the repo → never committed, never shared.
     A new team member cloning the repo will NOT see your personal-notes server.

  4. Claude Code merges both at startup. A developer gets both their personal
     servers AND the project servers.

  5. CRM_API_KEY uses ${ENV_VAR} syntax → the real secret stays in the shell
     environment, NOT in the file that gets committed.
""")


# ---------------------------------------------------------------------------
# PART B — Scoping demo (simulated)
# ---------------------------------------------------------------------------

def part_b_scoping():
    section("PART B: Scoping demo — what a new teammate sees")

    print("""
SCENARIO:
  Julia configures 3 MCP servers:
    • filesystem  → project-level (.mcp.json)
    • fetch       → project-level (.mcp.json)
    • internal-crm → project-level (.mcp.json)
    • personal-notes → user-level (~/.claude.json)

  New teammate Sam clones the repo. Sam has NO user-level ~/.claude.json yet.
""")

    julia_servers = set(PROJECT_MCP_JSON["mcpServers"].keys()) | \
                    set(USER_CLAUDE_JSON_SNIPPET["mcpServers"].keys())

    sam_servers = set(PROJECT_MCP_JSON["mcpServers"].keys())  # repo clone only

    print(f"  Julia sees:  {sorted(julia_servers)}")
    print(f"  Sam sees:    {sorted(sam_servers)}")
    print(f"\n  Sam is MISSING: {sorted(julia_servers - sam_servers)}")
    print("""
  WHY:
    personal-notes was configured in Julia's ~/.claude.json (user-level).
    That file lives on Julia's machine and is never committed.
    When Sam clones the repo, she only gets .mcp.json → project-level servers only.

  EXAM TRAP:
    "A teammate opens the project and doesn't see your MCP server."
    → You put it in user-level config instead of project-level.
    Fix: move it to .mcp.json if the whole team needs it.
""")


# ---------------------------------------------------------------------------
# PART C — Credential hygiene
# ---------------------------------------------------------------------------

BAD_CONFIG = {
    "mcpServers": {
        "internal-crm": {
            "command": "python",
            "args": ["-m", "crm_mcp_server"],
            "env": {
                "CRM_API_KEY": "sk-crm-REAL-SECRET-KEY-1234abcd"  # NEVER do this
            }
        }
    }
}

GOOD_CONFIG = {
    "mcpServers": {
        "internal-crm": {
            "command": "python",
            "args": ["-m", "crm_mcp_server"],
            "env": {
                "CRM_API_KEY": "${CRM_API_KEY}"  # expanded from shell env at startup
            }
        }
    }
}


def part_c_credentials():
    section("PART C: Credential hygiene")

    show_json("BAD — hardcoded secret (will be committed to git)", BAD_CONFIG)
    show_json("GOOD — env-var reference (secret stays out of version control)", GOOD_CONFIG)

    # Simulate env-var expansion
    os.environ.setdefault("CRM_API_KEY", "sk-crm-from-env-safe-to-use")

    expanded_value = os.environ.get("CRM_API_KEY", "<not set>")
    print(f"""
HOW ${"{CRM_API_KEY}"} EXPANSION WORKS:
  1. You set:   export CRM_API_KEY=sk-crm-from-env-safe-to-use
  2. .mcp.json stores: "${{CRM_API_KEY}}"
  3. Claude Code reads the file and expands to: "{expanded_value}"
  4. The MCP server process receives the real key via environment variable.
  5. The git-tracked file never contains the secret.

RISKS OF THE BAD CONFIG:
  • Anyone with repo access (now or in git history) sees the key.
  • Key rotation requires editing and re-committing the file.
  • If the repo is ever made public, the key is permanently exposed.
""")


# ---------------------------------------------------------------------------
# PART D — tools vs. resources
# ---------------------------------------------------------------------------

# In MCP, a server can expose both. The distinction matters for how Claude uses them.

EXAMPLE_TOOL_DEFINITION = {
    "name": "create_crm_contact",
    "description": "Create a new contact record in the CRM system.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "name":  {"type": "string"},
            "email": {"type": "string"},
            "company": {"type": "string"}
        },
        "required": ["name", "email"]
    }
}

EXAMPLE_RESOURCE_DEFINITION = {
    "uri": "crm://contacts/recent",
    "name": "Recent CRM contacts",
    "description": "Read-only snapshot of the 50 most recently added contacts.",
    "mimeType": "application/json"
}

TOOL_VS_RESOURCE_SCENARIOS = [
    ("Fetch today's exchange rates for context",    "resource", "Read-only, no side effects"),
    ("Send a Slack message to the team",             "tool",     "Write action with side effects"),
    ("Read a project README into context",           "resource", "Read-only file content"),
    ("Create a GitHub issue",                        "tool",     "Write action, modifies state"),
    ("Browse a list of open support tickets",        "resource", "Read-only enumeration"),
    ("Close a support ticket",                       "tool",     "State change, write action"),
]


def part_d_tools_vs_resources():
    section("PART D: tools vs. resources")

    show_json("Example MCP tool definition", EXAMPLE_TOOL_DEFINITION)
    show_json("Example MCP resource definition", EXAMPLE_RESOURCE_DEFINITION)

    print("""
CORE DISTINCTION:
  tools     → Claude CALLS them, they can have side effects (create, update, delete)
               Claude must decide WHEN to call them and with WHAT arguments.
               Appears in Claude's tool list; fires a tool_use stop_reason.

  resources → Claude READS them for context (like injecting a document)
               They are always read-only. No side effects.
               Claude Code can include resources as context without an explicit call.

DECISION RULE:
  "Does this operation change state in the external system?"
    YES → tool
    NO  → resource (prefer resource; lower risk, no accidental writes)
""")

    print("SCENARIO CLASSIFICATION:")
    print(f"  {'Scenario':<50} {'Type':<10} {'Reason'}")
    print(f"  {'-'*50} {'-'*10} {'-'*30}")
    for scenario, kind, reason in TOOL_VS_RESOURCE_SCENARIOS:
        print(f"  {scenario:<50} {kind:<10} {reason}")


# ---------------------------------------------------------------------------
# PART E — Community vs. custom MCP server decision tree
# ---------------------------------------------------------------------------

COMMUNITY_SERVERS = [
    "@modelcontextprotocol/server-filesystem",
    "@modelcontextprotocol/server-github",
    "@modelcontextprotocol/server-slack",
    "@modelcontextprotocol/server-postgres",
    "mcp-server-fetch",
    "mcp-server-brave-search",
]

DECISION_SCENARIOS = [
    {
        "scenario": "Give Claude access to read/write local project files",
        "decision": "community",
        "server":   "@modelcontextprotocol/server-filesystem",
        "reason":   "Exact match — maintained, battle-tested, no build cost."
    },
    {
        "scenario": "Connect Claude to your company's internal ticketing system (proprietary REST API)",
        "decision": "custom",
        "server":   "build: internal-tickets-mcp",
        "reason":   "No community server covers a proprietary internal API. "
                    "Custom server wraps your REST API and exposes only the tools you need."
    },
    {
        "scenario": "Let Claude fetch arbitrary web pages for research",
        "decision": "community",
        "server":   "mcp-server-fetch",
        "reason":   "mcp-server-fetch does exactly this. No reason to build."
    },
    {
        "scenario": "Access your ML model registry (internal, non-standard format)",
        "decision": "custom",
        "server":   "build: model-registry-mcp",
        "reason":   "Proprietary format + internal auth = community servers can't help. "
                    "Custom server gives you full control over schema and access patterns."
    },
]


def part_e_community_vs_custom():
    section("PART E: Community vs. custom MCP server decision tree")

    print(f"\nAvailable community MCP servers (sample):")
    for s in COMMUNITY_SERVERS:
        print(f"  • {s}")

    print("""
DECISION FRAMEWORK:
  Use community if:
    ✓ A well-maintained server already exists for this system
    ✓ The surface area matches what you need (not over/under-exposed)
    ✓ You don't have proprietary auth or data formats

  Build custom if:
    ✓ Proprietary internal system (no community server exists)
    ✓ Community server exposes too much (security surface) or too little
    ✓ You need custom auth, schema validation, or rate limiting
    ✓ You need to combine multiple internal APIs under one server
""")

    print("SCENARIO DECISIONS:")
    for item in DECISION_SCENARIOS:
        decision_label = "COMMUNITY" if item["decision"] == "community" else "CUSTOM  "
        print(f"\n  [{decision_label}] {item['scenario']}")
        print(f"    → {item['server']}")
        print(f"    Reason: {item['reason']}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Exercise 8: MCP Integration")
    print("============================")
    print("Choose which part to run:")
    print("  A   — MCP anatomy: project-level vs. user-level config structures")
    print("  B   — Scoping demo: what a new teammate sees after cloning")
    print("  C   — Credential hygiene: hardcoded vs. env-var reference")
    print("  D   — tools vs. resources: when to use each")
    print("  E   — Community vs. custom: 4 scenario decisions")
    print("  all — Run all parts in sequence")

    choice = input("\nEnter choice: ").strip().lower()

    dispatch = {
        "a":   part_a_anatomy,
        "b":   part_b_scoping,
        "c":   part_c_credentials,
        "d":   part_d_tools_vs_resources,
        "e":   part_e_community_vs_custom,
    }

    if choice == "all":
        for fn in dispatch.values():
            fn()
    elif choice in dispatch:
        dispatch[choice]()
    else:
        print("Unknown choice.")

    print("\n" + "="*60)
    print("REFLECTION QUESTIONS (answer in learnings.md):")
    print("="*60)
    print("""
1. A teammate opens the project and doesn't see your MCP server.
   Where did you most likely put the config?

2. Why should you never hardcode API keys directly in .mcp.json?

3. What is the difference between an MCP tool and an MCP resource?
   Give one example of each and explain the decision rule.

4. When is building a custom MCP server worth it vs. using an
   existing community one?

5. What is the scope difference between project-level and user-level
   MCP configs? Which gets version-controlled and why?
""")
