"""
Domain 1 Exercise 3: Multi-Agent Hub-and-Spoke Orchestration
=============================================================
CCA-F Topic: Agentic Architecture & Orchestration (27%)

Sessions 1–2 built a single-agent loop. Real production systems use
multiple Claude instances: one COORDINATOR that manages everything,
and SUBAGENTS that each do a focused task.

Key rule the exam tests heavily:
  Subagents do NOT automatically inherit the coordinator's context.
  Every piece of information a subagent needs must be explicitly passed.

Architecture pattern (hub-and-spoke):
  Coordinator
     ├── SubagentA  (knows only what coordinator told it)
     ├── SubagentB  (knows only what coordinator told it)
     └── SubagentC  (subagents NEVER talk to each other)

This exercise uses raw API calls to make the pattern visible.
Higher-level frameworks (Agent SDK) hide this, but the CCA tests
whether you understand what's happening underneath.

Run: python3 ex03_multi_agent.py
"""

import anthropic
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

client = anthropic.Anthropic()


# ---------------------------------------------------------------------------
# Simulated data sources (stand-ins for real APIs)
# ---------------------------------------------------------------------------

STOCK_DATA = {
    "AAPL": {"price": 189.50, "pe_ratio": 28.5, "market_cap": "2.9T", "sector": "Technology"},
    "GOOG": {"price": 175.20, "pe_ratio": 24.1, "market_cap": "2.1T", "sector": "Technology"},
    "MSFT": {"price": 415.00, "pe_ratio": 35.2, "market_cap": "3.1T", "sector": "Technology"},
}

NEWS_DATA = {
    "AAPL": "Apple reported record iPhone sales in Q1. Services revenue up 15% YoY.",
    "GOOG": "Google Cloud revenue surpassed $10B quarterly. AI integration across all products.",
    "MSFT": "Microsoft Azure growth accelerated. Copilot adoption driving enterprise deals.",
}


def fetch_stock_data(ticker: str) -> dict:
    return STOCK_DATA.get(ticker.upper(), {"error": f"No data for {ticker}"})


def fetch_news(ticker: str) -> str:
    return NEWS_DATA.get(ticker.upper(), f"No news available for {ticker}")


# ---------------------------------------------------------------------------
# A minimal single-agent call (no tools needed — subagents just reason)
# ---------------------------------------------------------------------------

def call_claude(system: str, user: str, label: str = "") -> str:
    """Single Claude call. Returns text response."""
    if label:
        print(f"\n  [{label}] calling Claude...")
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": user}]
    )
    return response.content[0].text


# ===========================================================================
# SECTION 1: The problem — subagents without explicit context
#
# A coordinator has a user request and some internal knowledge.
# It spawns a subagent WITHOUT passing that knowledge.
# The subagent operates blind.
# ===========================================================================
print("\n" + "#"*60)
print("# SECTION 1: Subagent WITHOUT explicit context (broken)")
print("#"*60)

# Coordinator gathers data (this knowledge lives only in the coordinator)
coordinator_context = {
    "user_goal": "Compare AAPL and GOOG for a long-term investor",
    "aapl_data": fetch_stock_data("AAPL"),
    "goog_data": fetch_stock_data("GOOG"),
    "aapl_news": fetch_news("AAPL"),
    "goog_news": fetch_news("GOOG"),
}

print(f"\n  Coordinator gathered data for AAPL and GOOG.")
print(f"  Now spawning a subagent WITHOUT passing that data...\n")

# Subagent receives NO context — only the bare task
subagent_response_no_context = call_claude(
    system="You are a financial analysis subagent.",
    user="Compare AAPL and GOOG for a long-term investor. Which is better?",
    label="subagent-no-context"
)

print(f"\n  SUBAGENT OUTPUT (no context):\n  {subagent_response_no_context[:400]}...")
print(f"\n  ^ Notice: subagent invents or hedges because it has no real data.")


# ===========================================================================
# SECTION 2: The fix — explicitly passing context to each subagent
#
# The coordinator packs everything the subagent needs into its prompt.
# This is the required pattern in all multi-agent systems.
# ===========================================================================
print("\n" + "#"*60)
print("# SECTION 2: Subagent WITH explicit context (correct)")
print("#"*60)

# Each subagent gets only what IT needs — no more, no less
aapl_prompt = f"""
You are a financial analysis subagent. Your task: analyze AAPL for a long-term investor.

Stock data:
{json.dumps(coordinator_context["aapl_data"], indent=2)}

Recent news:
{coordinator_context["aapl_news"]}

Produce a 3-bullet analysis covering: valuation, growth outlook, and risk.
"""

goog_prompt = f"""
You are a financial analysis subagent. Your task: analyze GOOG for a long-term investor.

Stock data:
{json.dumps(coordinator_context["goog_data"], indent=2)}

Recent news:
{coordinator_context["goog_news"]}

Produce a 3-bullet analysis covering: valuation, growth outlook, and risk.
"""

print("\n  Spawning AAPL subagent and GOOG subagent sequentially...")
aapl_analysis = call_claude(
    system="You are a financial analysis subagent.",
    user=aapl_prompt,
    label="subagent-AAPL"
)
goog_analysis = call_claude(
    system="You are a financial analysis subagent.",
    user=goog_prompt,
    label="subagent-GOOG"
)

print(f"\n  AAPL SUBAGENT OUTPUT:\n{aapl_analysis}")
print(f"\n  GOOG SUBAGENT OUTPUT:\n{goog_analysis}")


# ===========================================================================
# SECTION 3: Parallel subagent spawning
#
# Sequential spawning: total latency = latency_A + latency_B
# Parallel spawning:  total latency = max(latency_A, latency_B)
#
# Both subagents run in separate threads — same pattern as the Agent SDK's
# parallel Task calls, just made explicit here.
# Subagents still don't talk to each other — the coordinator collects both.
# ===========================================================================
print("\n" + "#"*60)
print("# SECTION 3: Parallel subagent spawning")
print("#"*60)

import time

def analyze_ticker(ticker: str) -> tuple[str, str]:
    """Subagent task: fetch data, call Claude, return (ticker, analysis)."""
    stock = fetch_stock_data(ticker)
    news = fetch_news(ticker)
    prompt = f"""
You are a financial analysis subagent. Analyze {ticker} for a long-term investor.

Stock data: {json.dumps(stock)}
News: {news}

Give a 2-sentence verdict: buy, hold, or avoid — and why.
"""
    analysis = call_claude(
        system="You are a financial analysis subagent.",
        user=prompt,
        label=f"parallel-subagent-{ticker}"
    )
    return ticker, analysis


tickers = ["AAPL", "GOOG", "MSFT"]

print(f"\n  Spawning {len(tickers)} subagents in parallel...")
t_start = time.time()

parallel_results = {}
with ThreadPoolExecutor(max_workers=len(tickers)) as executor:
    futures = {executor.submit(analyze_ticker, t): t for t in tickers}
    for future in as_completed(futures):
        ticker, analysis = future.result()
        parallel_results[ticker] = analysis
        print(f"  ✓ {ticker} subagent done")

t_parallel = time.time() - t_start
print(f"\n  All subagents finished in {t_parallel:.1f}s (parallel)")


# ===========================================================================
# SECTION 4: Coordinator aggregates results
#
# Subagents hand their outputs back to the coordinator.
# Only the coordinator synthesizes — subagents never see each other's output.
# ===========================================================================
print("\n" + "#"*60)
print("# SECTION 4: Coordinator aggregates subagent results")
print("#"*60)

aggregation_prompt = f"""
You are the coordinator of a multi-agent financial research system.
Three specialist subagents have analyzed three stocks independently.
Your job: synthesize their findings into a final recommendation.

SUBAGENT REPORTS:
{chr(10).join(f"--- {ticker} ---{chr(10)}{analysis}" for ticker, analysis in parallel_results.items())}

USER GOAL: Which of these three stocks is best for a long-term investor?

Provide a final ranked recommendation with a one-sentence rationale for each.
"""

print("\n  Coordinator synthesizing subagent outputs...")
final_recommendation = call_claude(
    system="You are a multi-agent research coordinator. Synthesize subagent reports into a final answer.",
    user=aggregation_prompt,
    label="coordinator-synthesis"
)

print(f"\n  COORDINATOR FINAL OUTPUT:\n{final_recommendation}")


# ===========================================================================
# SECTION 5: What the coordinator is responsible for
#             (visualising the hub-and-spoke contract)
# ===========================================================================
print("\n" + "#"*60)
print("# SECTION 5: Hub-and-spoke contract summary")
print("#"*60)
print("""
  COORDINATOR is responsible for:
    - Receiving the user's original goal
    - Task decomposition (deciding which subagents to spawn)
    - Explicitly injecting all context each subagent needs
    - Spawning subagents (sequentially or in parallel)
    - Collecting and aggregating results
    - Error handling if a subagent fails
    - Returning the final answer to the user

  SUBAGENTS are responsible for:
    - One focused task only
    - Using only the context they were given
    - Never talking to other subagents directly
    - Returning a result (or structured error) to the coordinator
""")

# ...existing code...

# ===========================================================================
# SECTION 6: Exception handling — what happens when a subagent fails?
#
# In Section 3, all subagents succeeded. Real production fails.
# The coordinator must handle three cases:
#   1. Transient failure (retry with backoff)
#   2. Validation failure (fix input, retry)
#   3. Permanent failure (graceful degradation)
#
# Anti-patterns to avoid:
#   1. Silent suppression: pretend failure didn't happen
#   2. Hard termination: abandon entire workflow
#
# Correct pattern: graceful degradation — return partial results + error
# ===========================================================================
print("\n" + "#"*60)
print("# SECTION 6: Exception handling in parallel subagents")
print("#"*60)


class SubagentFailure(Exception):
    """Represents a subagent failure with context."""
    def __init__(self, ticker: str, error_type: str, message: str, retry_count: int = 0):
        self.ticker = ticker
        self.error_type = error_type  # "transient", "validation", "permanent"
        self.message = message
        self.retry_count = retry_count
        super().__init__(f"[{ticker}] {error_type}: {message}")


def analyze_ticker_with_errors(ticker: str, simulate_error: str = None, retry_count: int = 0) -> dict:
    """
    Subagent task with error handling.
    
    Returns:
        {
            "ticker": str,
            "status": "success" | "error",
            "analysis": str (if success),
            "error": {"type": str, "message": str, "retry_count": int} (if error)
        }
    """
    try:
        # Simulate different failure modes
        if simulate_error == "transient" and retry_count < 2:
            raise SubagentFailure(
                ticker,
                "transient",
                "API rate limit hit — temporary failure",
                retry_count
            )
        
        if simulate_error == "validation":
            raise SubagentFailure(
                ticker,
                "validation",
                f"Invalid ticker format: '{ticker}' — expected uppercase",
                retry_count
            )
        
        if simulate_error == "permanent":
            raise SubagentFailure(
                ticker,
                "permanent",
                f"Ticker '{ticker}' not found in data source",
                retry_count
            )
        
        # Normal execution path
        stock = fetch_stock_data(ticker)
        news = fetch_news(ticker)
        
        if "error" in stock:
            raise SubagentFailure(ticker, "validation", stock["error"])
        
        prompt = f"""
You are a financial analysis subagent. Analyze {ticker} for a long-term investor.

Stock data: {json.dumps(stock)}
News: {news}

Give a 2-sentence verdict: buy, hold, or avoid — and why.
"""
        analysis = call_claude(
            system="You are a financial analysis subagent.",
            user=prompt,
            label=f"error-handling-{ticker}"
        )
        
        return {
            "ticker": ticker,
            "status": "success",
            "analysis": analysis,
            "error": None,
        }
    
    except SubagentFailure as e:
        return {
            "ticker": ticker,
            "status": "error",
            "analysis": None,
            "error": {
                "type": e.error_type,
                "message": e.message,
                "retry_count": retry_count,
            }
        }
    
    except Exception as e:
        # Catch-all for unexpected errors
        return {
            "ticker": ticker,
            "status": "error",
            "analysis": None,
            "error": {
                "type": "unexpected",
                "message": str(e),
                "retry_count": retry_count,
            }
        }


def coordinator_with_retry_logic(tickers: list, simulate_errors: dict = None) -> dict:
    """
    Coordinator that spawns subagents in parallel and handles failures.
    
    Args:
        tickers: list of ticker symbols
        simulate_errors: {"GOOG": "transient", "MSFT": "permanent", ...}
    
    Returns:
        {
            "successful": [results],
            "failed": [results],
            "partial_aggregation": str (synthesis of what succeeded)
        }
    """
    simulate_errors = simulate_errors or {}
    
    print(f"\n  Spawning {len(tickers)} subagents with error simulation...")
    print(f"  Error scenarios: {simulate_errors}")
    
    results_by_ticker = {}
    
    with ThreadPoolExecutor(max_workers=len(tickers)) as executor:
        futures = {}
        for ticker in tickers:
            error_mode = simulate_errors.get(ticker)
            future = executor.submit(
                analyze_ticker_with_errors,
                ticker,
                simulate_error=error_mode,
                retry_count=0
            )
            futures[future] = ticker
        
        for future in as_completed(futures):
            ticker = futures[future]
            result = future.result()
            results_by_ticker[ticker] = result
            
            if result["status"] == "success":
                print(f"  ✓ {ticker} succeeded")
            else:
                print(f"  ✗ {ticker} failed: {result['error']['type']}")
    
    # Separate successful from failed
    successful = [r for r in results_by_ticker.values() if r["status"] == "success"]
    failed = [r for r in results_by_ticker.values() if r["status"] == "error"]
    
    print(f"\n  Results: {len(successful)} successful, {len(failed)} failed")
    
    # Handle retries for transient failures
    print(f"\n  Retrying transient failures...")
    retried_results = []
    for failed_result in failed[:]:
        if failed_result["error"]["type"] == "transient" and failed_result["error"]["retry_count"] < 2:
            ticker = failed_result["ticker"]
            print(f"    Retrying {ticker}...")
            retry_result = analyze_ticker_with_errors(
                ticker,
                simulate_error="transient",
                retry_count=failed_result["error"]["retry_count"] + 1
            )
            if retry_result["status"] == "success":
                print(f"    ✓ {ticker} succeeded on retry")
                successful.append(retry_result)
                failed.remove(failed_result)
                retried_results.append(retry_result)
            else:
                print(f"    ✗ {ticker} still failing")
    
    # PATTERN: Graceful degradation
    # Don't halt — synthesize what we have, note what failed
    
    if successful:
        partial_aggregation_prompt = f"""
You are the coordinator of a multi-agent financial research system.
Some specialist subagents have analyzed stocks. Others failed.

SUCCESSFUL REPORTS:
{chr(10).join(f"--- {r['ticker']} ---{chr(10)}{r['analysis']}" for r in successful)}

FAILED ANALYSES:
{chr(10).join(f"--- {r['ticker']}: {r['error']['type']} ---" for r in failed)}

Synthesize the successful analyses into a recommendation.
Note which stocks we couldn't analyze and why.
"""
        partial_aggregation = call_claude(
            system="You are a coordinator. Synthesize partial results gracefully.",
            user=partial_aggregation_prompt,
            label="coordinator-partial-synthesis"
        )
    else:
        partial_aggregation = f"All subagents failed. Unable to produce analysis. Failures:\n" + \
            "\n".join(f"  - {r['ticker']}: {r['error']['message']}" for r in failed)
    
    return {
        "successful": successful,
        "failed": failed,
        "partial_aggregation": partial_aggregation,
    }


# Run the error handling scenario
print("\n  Scenario: GOOG subagent experiences transient failure, MSFT experiences permanent failure")
error_results = coordinator_with_retry_logic(
    ["AAPL", "GOOG", "MSFT"],
    simulate_errors={
        "GOOG": "transient",  # Will fail once, then succeed on retry
        "MSFT": "permanent",  # Will keep failing
    }
)

print(f"\n  SUCCESSFUL ANALYSES ({len(error_results['successful'])}):")
for r in error_results["successful"]:
    print(f"    {r['ticker']}: {r['analysis'][:80]}...")

print(f"\n  FAILED ANALYSES ({len(error_results['failed'])}):")
for r in error_results["failed"]:
    print(f"    {r['ticker']}: {r['error']['message']}")

print(f"\n  COORDINATOR PARTIAL SYNTHESIS:\n{error_results['partial_aggregation']}")

# ===========================================================================
# SECTION 7: Anti-patterns illustrated
# ===========================================================================
print("\n" + "#"*60)
print("# SECTION 7: Anti-patterns to AVOID")
print("#"*60)
print("""
  ANTI-PATTERN 1: Silent Suppression
  -----------------------------------
  ✗ WRONG:
      if result["status"] == "error":
          continue  # Skip this result entirely
      # Later: synthesize only successful subagents
      # Problem: Coordinator doesn't report that GOOG failed!
      # User thinks all stocks were analyzed. Hallucination risk.

  ✓ CORRECT:
      if result["status"] == "error":
          error_context.append(result)
      # Coordinator includes: "GOOG analysis failed because..."
      # User sees partial results transparently.


  ANTI-PATTERN 2: Hard Termination
  ---------------------------------
  ✗ WRONG:
      if any subagent fails:
          raise Exception("Workflow aborted")
      # Problem: AAPL and MSFT succeeded! Lose that value.

  ✓ CORRECT:
      if any subagent fails:
          log it + continue
      # Synthesize what succeeded + flag what failed
      # Graceful degradation maintains value.


  THE CORRECT PATTERN: Graceful Degradation
  ------------------------------------------
  1. Spawn all subagents in parallel (or serial)
  2. Classify each result:
     - Success → include in synthesis
     - Transient error → retry with backoff
     - Validation error → fix input, retry
     - Permanent error → log, skip, continue
  3. Synthesize ONLY successful results
  4. Report which analyses were unavailable and why
  5. Return to user: (partial_results, errors_encountered)
""")

# ...existing code...


# ---------------------------------------------------------------------------
# REFLECTION QUESTIONS
# ---------------------------------------------------------------------------
# After running, answer these in learnings.md:
#
# 1. In Section 1, the subagent had no real stock data. What did it do instead?
#    What is the production risk if you ship this pattern?
#
# 2. In Section 2, each subagent prompt includes only the data for its own ticker.
#    Why NOT pass BOTH tickers' data to each subagent?
#
# 3. Section 3 runs 3 subagents in parallel using threads.
#    In the Anthropic Agent SDK, what mechanism replaces ThreadPoolExecutor?
#    (Hint: look at the learning-plan.md notes on "Task tool")
#
# 4. If the GOOG subagent in Section 3 throws an exception, what should the
#    coordinator do? What are the two anti-patterns to avoid?
#    (Hint: revisit Session 17's topic in the learning plan)
#
# 5. Could you build this same system using parallel tool calls from Session 2
#    instead of spawning separate Claude instances?
#    What would you gain? What would you lose?



"""
Agent SDK Task Tool: Parallel Subagent Execution
================================================
Shows how the Agent SDK's Task tool replaces manual ThreadPoolExecutor.

Key difference from ex03_multi_agent.py:
- ex03: raw API calls + manual threading (ThreadPoolExecutor)
- This: Agent SDK abstracts threading — you just define Tasks and let the framework parallelize

Install: pip install anthropic-sdk
Run: python3 agent_sdk_task_example.py
"""

# from anthropic_sdk import Anthropic

# client = Anthropic()

# # ---------------------------------------------------------------------------
# # Define subagent tasks using the Task tool
# # ---------------------------------------------------------------------------

# tasks = [
#     {
#         "name": "analyze_aapl",
#         "description": "Analyze Apple stock for a long-term investor",
#         "input_schema": {
#             "type": "object",
#             "properties": {
#                 "stock_data": {"type": "string", "description": "Stock metrics (price, PE ratio, market cap)"},
#                 "news": {"type": "string", "description": "Recent news about the company"},
#             },
#             "required": ["stock_data", "news"],
#         },
#     },
#     {
#         "name": "analyze_goog",
#         "description": "Analyze Google stock for a long-term investor",
#         "input_schema": {
#             "type": "object",
#             "properties": {
#                 "stock_data": {"type": "string", "description": "Stock metrics (price, PE ratio, market cap)"},
#                 "news": {"type": "string", "description": "Recent news about the company"},
#             },
#             "required": ["stock_data", "news"],
#         },
#     },
#     {
#         "name": "analyze_msft",
#         "description": "Analyze Microsoft stock for a long-term investor",
#         "input_schema": {
#             "type": "object",
#             "properties": {
#                 "stock_data": {"type": "string", "description": "Stock metrics (price, PE ratio, market cap)"},
#                 "news": {"type": "string", "description": "Recent news about the company"},
#             },
#             "required": ["stock_data", "news"],
#         },
#     },
# ]

# # ---------------------------------------------------------------------------
# # Coordinator loop: spawn parallel Tasks and collect results
# # ---------------------------------------------------------------------------

# print("\n" + "="*60)
# print("Agent SDK Task Tool: Parallel Subagent Spawning")
# print("="*60)

# coordinator_prompt = """
# You are a research coordinator. A user wants to compare three stocks: AAPL, GOOG, and MSFT.

# Your job:
# 1. Call ALL THREE analysis tasks in parallel (in a single response).
# 2. Each task receives its own stock data and news.
# 3. Do NOT wait for results between tasks — invoke all three at once.

# After all tasks return, synthesize their outputs into a final recommendation.

# Stock data:
# - AAPL: price=$189.50, PE=28.5, market_cap=$2.9T | News: Record iPhone sales, Services +15% YoY
# - GOOG: price=$175.20, PE=24.1, market_cap=$2.1T | News: Cloud revenue $10B+, AI integration
# - MSFT: price=$415.00, PE=35.2, market_cap=$3.1T | News: Azure acceleration, Copilot adoption

# Invoke the three analysis tasks now (in parallel, not sequentially).
# Then wait for all results and produce a final ranking.
# """

# messages = [{"role": "user", "content": coordinator_prompt}]

# # Agentic loop
# while True:
#     print(f"\n[Coordinator turn] Calling Claude...")
    
#     response = client.messages.create(
#         model="claude-haiku-4-5",
#         max_tokens=2048,
#         tools=tasks,
#         messages=messages,
#     )
    
#     print(f"  stop_reason: {response.stop_reason}")
    
#     # Check if Claude wants to call tasks
#     if response.stop_reason == "tool_use":
#         # Collect all tool calls from this response
#         tool_calls = [block for block in response.content if block.type == "tool_use"]
#         print(f"  Claude invoked {len(tool_calls)} task(s): {[tc.name for tc in tool_calls]}")
        
#         # Add Claude's response (with all tool_use blocks) to messages
#         messages.append({"role": "assistant", "content": response.content})
        
#         # Simulate task execution (in real SDK, these would run in parallel)
#         # Each task returns a result
#         tool_results = []
#         for tool_call in tool_calls:
#             # Simulate task execution
#             if tool_call.name == "analyze_aapl":
#                 result = "AAPL: Valuation stretched (PE 28.5), but Services growth strong. Steady hold."
#             elif tool_call.name == "analyze_goog":
#                 result = "GOOG: Fair valuation (PE 24.1), Cloud upside. Strong buy."
#             elif tool_call.name == "analyze_msft":
#                 result = "MSFT: Premium valuation (PE 35.2), but Copilot TAM enormous. Buy."
#             else:
#                 result = "Unknown task"
            
#             tool_results.append({
#                 "type": "tool_result",
#                 "tool_use_id": tool_call.id,
#                 "content": result,
#             })
#             print(f"    ✓ {tool_call.name} completed")
        
#         # Add all tool results in a single user message
#         messages.append({"role": "user", "content": tool_results})
#         print(f"  All {len(tool_results)} task results returned to coordinator")
    
#     elif response.stop_reason == "end_turn":
#         # Claude finished reasoning — extract final answer
#         final_text = next(
#             (block.text for block in response.content if hasattr(block, "text")),
#             None
#         )
#         print(f"\n[Coordinator final output]:\n{final_text}")
#         break
    
#     else:
#         print(f"  Unexpected stop_reason: {response.stop_reason}")
#         break

# # ---------------------------------------------------------------------------
# # KEY DIFFERENCES from ex03_multi_agent.py (raw API + threading)
# # ---------------------------------------------------------------------------
# print("\n" + "="*60)
# print("Comparison: Raw API vs Agent SDK")
# print("="*60)
# print("""
# RAW API (ex03_multi_agent.py):
#   - Manually spawn threads with ThreadPoolExecutor
#   - Coordinate timing yourself
#   - Handle thread exceptions
#   - Build aggregation logic manually

# AGENT SDK Task Tool (this file):
#   - Define tasks once
#   - Claude decides to invoke all three in parallel (one response)
#   - SDK handles scheduling and result collection
#   - Claude itself orchestrates aggregation

# KEY INSIGHT:
#   In BOTH cases, parallelization happens in ONE round-trip:
#   - Raw API: ThreadPoolExecutor runs tasks concurrently, single return
#   - Agent SDK: Claude invokes 3 Task tools in one turn, SDK runs in parallel

#   The SDK just abstracts away the threading mechanics.
# """)
