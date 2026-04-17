"""
Tool-calling client for a vLLM server deployed with --enable-auto-tool-choice.
File: examples/basic-deployment/tool_calling_client.py

Demonstrates the two-turn agent loop with an OpenAI-compatible endpoint:
  1. Client sends messages + `tools` schema to the model
  2. Model responds with one or more `tool_calls` (no visible content)
  3. Client executes the tool(s) locally
  4. Client sends tool results back as `role: "tool"` messages
  5. Model uses the results to produce a final answer

Requires the server to be deployed with both:
  --enable-auto-tool-choice        (so `tool_choice: "auto"` is honored)
  --tool-call-parser gemma4        (the model-specific parser; minimax/mistral for those)

All three server examples in this skill have these flags enabled by default.

Usage:
    BASE_URL=https://<workspace>--gemma-4-vllm-server-serve.modal.run/v1 \\
        python examples/basic-deployment/tool_calling_client.py

    # With Modal proxy auth:
    BASE_URL=https://<workspace>--gemma-4-secured-vllm-serve.modal.run/v1 \\
    MODAL_TOKEN_ID=wk-... MODAL_TOKEN_SECRET=ws-... \\
        python examples/basic-deployment/tool_calling_client.py

vLLM tool-call format reference: https://docs.vllm.ai/en/latest/features/tool_calling.html
OpenAI tool-call spec:            https://platform.openai.com/docs/guides/function-calling
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "llm")
API_KEY = os.environ.get("API_KEY", "dummy")

# Optional Modal proxy auth — mirrors test_client.py
_headers: dict[str, str] = {}
if os.environ.get("MODAL_TOKEN_ID") and os.environ.get("MODAL_TOKEN_SECRET"):
    _headers = {
        "Modal-Key": os.environ["MODAL_TOKEN_ID"],
        "Modal-Secret": os.environ["MODAL_TOKEN_SECRET"],
    }


# ──────────────────────────────────────────────────────────────────────
# Tool definitions — what the model can call
# ──────────────────────────────────────────────────────────────────────
# Each tool has (a) a JSON-schema spec that goes to the model, and
# (b) a local Python function that actually runs when the model picks it.

TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Return the current UTC time as an ISO-8601 string.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Return a (fake) weather report for a named city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name, e.g. 'Toronto' or 'Paris'",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit",
                    },
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluate a basic arithmetic expression. Supports + - * / ** and parentheses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Arithmetic expression, e.g. '(17 * 23) + 5'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]


def tool_get_current_time() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def tool_get_weather(city: str, unit: str = "celsius") -> dict[str, Any]:
    # Stub — in a real app this would hit a weather API.
    # For this skill it just demonstrates the loop; the model can't tell the difference.
    fake_data = {
        "Toronto":  {"celsius": 4,  "fahrenheit": 39, "condition": "light snow"},
        "Paris":    {"celsius": 12, "fahrenheit": 54, "condition": "overcast"},
        "Tokyo":    {"celsius": 18, "fahrenheit": 64, "condition": "clear"},
    }
    entry = fake_data.get(city, {"celsius": 15, "fahrenheit": 59, "condition": "unknown"})
    return {
        "city": city,
        "unit": unit,
        "temperature": entry[unit],
        "condition": entry["condition"],
    }


def tool_calculate(expression: str) -> dict[str, Any]:
    """Evaluate a restricted arithmetic expression safely.
    This is a toy — don't use eval() with untrusted input in real code."""
    allowed = set("0123456789+-*/(). ")
    if not set(expression).issubset(allowed):
        return {"error": f"expression contains disallowed characters: {expression!r}"}
    try:
        result = eval(expression, {"__builtins__": {}}, {})  # noqa: S307 - restricted input
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


TOOL_DISPATCH = {
    "get_current_time": tool_get_current_time,
    "get_weather":      tool_get_weather,
    "calculate":        tool_calculate,
}


def execute_tool_call(tool_call: Any) -> str:
    """Run a single tool call and return the result as a JSON string.
    The model sees whatever string we return, so structured JSON is best."""
    name = tool_call.function.name
    args = json.loads(tool_call.function.arguments or "{}")
    fn = TOOL_DISPATCH.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool: {name}"})
    try:
        result = fn(**args)
    except TypeError as e:
        # Wrong/missing arguments — return as tool error, not exception.
        return json.dumps({"error": f"bad arguments for {name}: {e}"})
    return json.dumps(result) if not isinstance(result, str) else json.dumps({"value": result})


# ──────────────────────────────────────────────────────────────────────
# The agent loop
# ──────────────────────────────────────────────────────────────────────

def run_agent_turn(
    client: OpenAI,
    user_message: str,
    max_tool_rounds: int = 4,
    verbose: bool = True,
) -> str:
    """Run a single user request through the tool-calling loop until the model
    produces a non-tool-call response, or until max_tool_rounds is hit."""

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant with access to tools. "
                "When a user question requires real-time data, computation, or "
                "lookups, use the appropriate tool. Explain your reasoning briefly "
                "after receiving tool results."
            ),
        },
        {"role": "user", "content": user_message},
    ]

    for round_idx in range(max_tool_rounds):
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto",
            max_tokens=1024,
        )

        msg = response.choices[0].message

        if not msg.tool_calls:
            if verbose:
                print(f"  [round {round_idx}] final response")
            return msg.content or ""

        # Model wants to call one or more tools.
        # Append the assistant's tool-calling message to history exactly as it came back.
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        })

        # Execute each tool call and append the result.
        for tc in msg.tool_calls:
            result_str = execute_tool_call(tc)
            if verbose:
                args_preview = tc.function.arguments[:80].replace("\n", " ")
                result_preview = result_str[:80].replace("\n", " ")
                print(f"  [round {round_idx}] {tc.function.name}({args_preview}) -> {result_preview}")
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })

    return "(max tool rounds reached without final response)"


def main() -> int:
    if BASE_URL == "http://localhost:8000/v1":
        print("Warning: BASE_URL not set, defaulting to localhost.", file=sys.stderr)

    if _headers:
        print("Modal proxy auth: enabled\n")

    client = OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        default_headers=_headers or None,
    )

    test_queries = [
        "What time is it right now?",
        "What's the weather in Toronto in celsius?",
        "Compute (17 * 23) + 5 and tell me if the result is prime.",
        "Compare the weather in Paris and Tokyo right now — which is warmer?",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"━━━ Test {i}: {query}")
        try:
            answer = run_agent_turn(client, query)
            print(f"  → {answer}\n")
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}\n")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
