"""
Domain 1 Exercise 2: Tool Choice & Parallel Tool Calls
========================================================
CCA-F Topics: Tool Selection Control, Parallel Tool Execution

In Session 1 you built the loop. Now we go deeper into HOW Claude
decides to use tools — and how you as a developer can control that.

Key concepts:
  - tool_choice: controls whether/which tools Claude can use
  - Parallel tool calls: Claude calling multiple tools in ONE turn
  - Why this matters for latency and correctness in production agents

TASK: Run each section, observe the output, answer reflection questions.

Run: python ex02_tool_choice_parallel.py
"""

import anthropic
import json
import time

client = anthropic.Anthropic()

tools = [
    {
        "name": "get_weather",
        "description": "Returns current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name e.g. 'Berlin'"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "get_stock_price",
        "description": "Returns the current stock price for a ticker symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker e.g. 'AAPL'"}
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "calculator",
        "description": "Performs arithmetic. Use for any math calculation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression e.g. '12 * 7'"}
            },
            "required": ["expression"]
        }
    }
]


# --- Simulated tool implementations ---

def calculator(expression: str) -> str:
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def get_weather(city: str) -> str:
    fake_data = {"berlin": "12°C, cloudy", "tokyo": "22°C, sunny", "london": "9°C, rainy"}
    return fake_data.get(city.lower(), f"No data for {city}")


def get_stock_price(ticker: str) -> str:
    fake_prices = {"AAPL": "$189.50", "GOOG": "$175.20", "MSFT": "$415.00"}
    return fake_prices.get(ticker.upper(), f"Unknown ticker: {ticker}")


def execute_tool(name: str, inputs: dict) -> str:
    if name == "calculator":
        return calculator(inputs["expression"])
    elif name == "get_weather":
        return get_weather(inputs["city"])
    elif name == "get_stock_price":
        return get_stock_price(inputs["ticker"])
    return f"Unknown tool: {name}"


# --- Minimal agentic loop (reused from Session 1) ---

def run_agent(user_message: str, tool_choice=None, label="", skip_tool_result=None) -> str:
    print(f"\n{'='*55}")
    print(f"[{label}] USER: {user_message}")
    if tool_choice:
        print(f"  tool_choice: {tool_choice}")
    print('='*55)

    messages = [{"role": "user", "content": user_message}]

    turn = 0
    while True:
        turn += 1
        
         # Build kwargs fresh each turn
        kwargs = {
            "model": "claude-haiku-4-5",
            "max_tokens": 1024,
            "tools": tools,
            "messages": messages
        }
        
        # Only add tool_choice on the FIRST turn
        if tool_choice and turn == 1:
            kwargs["tool_choice"] = tool_choice
            
        response = client.messages.create(**kwargs)
        print(f"  [Turn {turn}] stop_reason={response.stop_reason}")

        if response.stop_reason == "end_turn":
            final_text = next(
                (block.text for block in response.content if hasattr(block, "text")), ""
            )
            print(f"  CLAUDE: {final_text}")
            return final_text

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            print(f"  [Turn {turn}] tool_use={response.content}")

            # Count how many tool calls are in this single response
            tool_calls = [b for b in response.content if b.type == "tool_use"]
            print(f"  Tools called in this turn: {len(tool_calls)}")

            tool_results = []
            for block in tool_calls:
                print(f"    -> {block.name}({json.dumps(block.input)})")
                
                # Skip this tool result if specified (for testing partial results)
                if skip_tool_result and block.name == skip_tool_result:
                    print(f"       [SKIPPING RESULT FOR {block.name}]")
                    continue
                
                result = execute_tool(block.name, block.input)
                print(f"       result: {result}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })

            messages.append({"role": "user", "content": tool_results})
            kwargs["messages"] = messages
        else:
            break

    return ""


# ===========================================================
# SECTION 1: tool_choice = "auto" (default)
# Claude decides whether to call a tool or not.
# ===========================================================
print("\n" + "#"*55)
print("# SECTION 1: tool_choice='auto' (default behavior)")
print("#"*55)

# Claude won't use a tool here — it knows the answer
run_agent("What is the capital of France?", label="auto - no tool needed")

# Claude will use calculator
run_agent("What is 347 * 82?", label="auto - tool needed")


# ===========================================================
# SECTION 2: tool_choice = {"type": "any"}
# Claude MUST call at least one tool — even when it doesn't need to.
# ===========================================================
print("\n" + "#"*55)
print("# SECTION 2: tool_choice={'type': 'any'} (force tool use)")
print("#"*55)

# Even though Claude knows the capital of France, it must call a tool.
# Watch what tool it picks and how it handles the result.
run_agent(
    "What is the capital of France?",
    tool_choice={"type": "any"},
    label="any - forced tool use"
)


# ===========================================================
# SECTION 3: tool_choice = {"type": "tool", "name": "calculator"}
# Claude MUST call this specific tool.
# ===========================================================
print("\n" + "#"*55)
print("# SECTION 3: tool_choice={'type': 'tool', 'name': 'calculator'}")
print("#"*55)

# Forcing a specific tool — useful for structured output / guaranteed schema
run_agent(
    "What's the weather like today?",    # weather question, but we force calculator
    tool_choice={"type": "tool", "name": "get_stock_price"},
    label="forced specific tool"
)


# ===========================================================
# SECTION 4: Parallel tool calls
# One user request → Claude calls multiple tools IN THE SAME TURN.
# This is a critical performance pattern: no sequential round-trips.
# ===========================================================
print("\n" + "#"*55)
print("# SECTION 4: Parallel tool calls")
print("#"*55)

# This should trigger 3 tool calls in a single turn
run_agent(
    "What's the weather in Tokyo and London, and what is AAPL's stock price?",
    label="parallel tool calls"
)


# ===========================================================
# SECTION 4B: Parallel tool calls WITH PARTIAL RESULTS
# What happens when you skip returning a result for one tool?
# ===========================================================
print("\n" + "#"*55)
print("# SECTION 4B: Parallel tool calls - SKIP ONE RESULT")
print("#"*55)

# Call 3 tools, but only return results for 2 of them
run_agent(
    "What's the weather in Tokyo and London, and what is AAPL's stock price?",
    label="parallel - skip get_stock_price result",
    skip_tool_result="get_stock_price"
)


# ===========================================================
# SECTION 5: Disable tools entirely
# tool_choice = {"type": "none"} — Claude answers from knowledge only.
# ===========================================================
print("\n" + "#"*55)
print("# SECTION 5: tool_choice={'type': 'none'} (no tools allowed)")
print("#"*55)

run_agent(
    "What is 100 * 42?",
    tool_choice={"type": "none"},
    label="no tools - answers from knowledge"
)


# --- REFLECTION QUESTIONS ---
#
# 1. In Section 2, what tool did Claude call when forced with "any"
#    for a question it could answer directly? Why that one?
#
# 2. In Section 3, what did Claude pass to the calculator when asked
#    about the weather? What does this reveal about how "forced tool use" works?
#
# 3. In Section 4, did Claude make 3 separate API calls or 1?
#    Why does this matter for latency in production agents?
#
# 4. When would you use tool_choice="none" in a real agent?
#    (Think about safety or multi-step pipelines.)
#
# 5. If Claude calls 3 tools in parallel (Section 4), how many
#    tool_result blocks go in the next user message? What happens
#    if you only return results for 2 of them?
