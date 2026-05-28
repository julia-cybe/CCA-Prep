"""
Domain 1 Exercise 1: The Agentic Loop
======================================
CCA-F Topic: Agentic Architecture & Orchestration

An "agentic loop" is the core pattern behind all multi-agent systems:
  1. Send a message to Claude with available tools
  2. Claude either responds with text (done) OR requests a tool call
  3. If tool call → execute it, send result back → repeat

This exercise builds the loop from scratch so you understand what
higher-level frameworks are hiding from you.

TASK: Run this script and observe how Claude decides when to call tools
vs when to stop. Then answer the reflection questions at the bottom.

Run: python ex01_agentic_loop.py
"""

import anthropic
import json

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

# --- Tool definitions ---
# Tools are described in JSON schema. Claude reads the description
# to decide WHEN and HOW to call each tool.

tools = [
    {
        "name": "calculator",
        "description": "Performs basic arithmetic. Use this whenever the user asks for a calculation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "A math expression like '12 * 7' or '100 / 4 + 3'"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "get_weather",
        "description": "Returns the current weather for a city. Use this when asked about weather.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city name, e.g. 'Berlin' or 'Tokyo'"
                }
            },
            "required": ["city"]
        }
    }
]


# --- Tool implementations (simulated) ---

def calculator(expression: str) -> str:
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def get_weather(city: str) -> str:
    # Simulated — in production this would hit a real API
    fake_data = {
        "berlin": "12°C, partly cloudy",
        "tokyo": "22°C, sunny",
        "london": "9°C, rainy",
    }
    return fake_data.get(city.lower(), f"Weather data unavailable for {city}")


def execute_tool(name: str, inputs: dict) -> str:
    if name == "calculator":
        return calculator(inputs["expression"])
    elif name == "get_weather":
        return get_weather(inputs["city"])
    else:
        return f"Unknown tool: {name}"


# --- The agentic loop ---

def run_agent(user_message: str) -> str:
    """
    Runs the full agentic loop for a single user request.
    Returns Claude's final text response.
    """
    print(f"\n{'='*50}")
    print(f"USER: {user_message}")
    print('='*50)

    messages = [{"role": "user", "content": user_message}]
    turn = 0

    while True:
        turn += 1
        print(f"\n[Turn {turn}] Calling Claude...")

        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            temperature=0,
            system="you are a helpful assistant trying to be funny",
            tools=tools,
            messages=messages
        )

        print(f"  stop_reason: {response.stop_reason}")
        
        print(response)

        # If Claude is done (no more tool calls), extract and return text
        if response.stop_reason == "end_turn":
            final_text = next(
                (block.text for block in response.content if hasattr(block, "text")),
                ""
            )
            print(f"\nCLAUDE: {final_text}")
            return final_text

        # Claude wants to use tools → stop_reason == "tool_use"
        if response.stop_reason == "tool_use":
            # Add Claude's response (including tool_use blocks) to message history
            messages.append({"role": "assistant", "content": response.content})

            # Process each tool call and collect results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  TOOL CALL: {block.name}({json.dumps(block.input)})")
                    result = execute_tool(block.name, block.input)
                    print(f"  TOOL RESULT: {result}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            # Add tool results back as a user message
            messages.append({"role": "user", "content": tool_results})

        else:
            # Unexpected stop reason
            print(f"  Unexpected stop_reason: {response.stop_reason}")
            break

    return ""


# --- Test cases ---

if __name__ == "__main__":
    # Test 1: No tool needed
    run_agent("What is the capital of France?")

    # Test 2: Single tool call
    run_agent("What is 347 multiplied by 82?")

    # Test 3: Multiple tool calls in sequence
    run_agent("What's the weather in Tokyo and Berlin, and what is 15% of 200?")


# --- REFLECTION QUESTIONS ---
# After running, think through these — they map directly to CCA-F Domain 1 questions:
#
# 1. What determines when Claude calls a tool vs responds with text?
#    (Hint: look at the tool descriptions)
#
# 2. Why does the tool result get sent back as role="user", not role="assistant"?
#    (Hint: who is "speaking" when a tool returns a result?)
#
# 3. What would happen if you forgot to add response.content to messages
#    before sending tool results? (Try it!)
#
# 4. The loop runs until stop_reason == "end_turn". What other stop_reason
#    values exist, and when would you see them in production?
#
# 5. Is this loop stateful or stateless across multiple user turns?
#    How would you make it stateful (i.e., remember previous conversations)?
