import json
import os
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT")
MODEL = os.getenv("MODEL")

if not OLLAMA_ENDPOINT:
    raise RuntimeError("OLLAMA_ENDPOINT is missing from the .env file.")

if not MODEL:
    raise RuntimeError("MODEL is missing from the .env file.")

SYSTEM_PROMPT = """
You are an internal IT support agent.

Available tools:

1. get_current_time
   Use when the user asks for the current time.

2. get_system_status
   Use when the user asks about VPN, Power BI, Email, or SAP status.

Return only valid JSON using one of these formats:

{
  "action": "tool",
  "tool_name": "get_current_time",
  "arguments": {}
}

{
  "action": "tool",
  "tool_name": "get_system_status",
  "arguments": {
    "system_name": "VPN"
  }
}

{
  "action": "answer",
  "answer": "Your response"
}

Do not include Markdown or additional text.
Do not invent system status or current time.
"""


def parse_decision(text: str) -> dict | None:
    stripped = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")

    try:
        decision = json.loads(stripped)
    except json.JSONDecodeError:
        return None

    return decision if isinstance(decision, dict) else None


def extract_answer(text: str) -> str:
    decision = parse_decision(text)

    if decision and "answer" in decision:
        return str(decision["answer"])

    return text.strip()


def get_current_time() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%I:%M %p")


def get_system_status(system_name: str) -> str:
    if not system_name or not system_name.strip():
        return "Error: system_name is required."

    systems = {
        "vpn": "Degraded",
        "power bi": "Operational",
        "email": "Operational",
        "sap": "Outage",
    }

    normalized_name = system_name.strip().lower()

    if normalized_name not in systems:
        return f"Unknown system: {system_name}"

    return systems[normalized_name]


TOOLS = {
    "get_current_time": lambda arguments: get_current_time(),
    "get_system_status": lambda arguments: get_system_status(
        arguments.get("system_name", "")
    ),
}


def ask_llm(prompt: str) -> dict:
    payload = {
        "model": MODEL,
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "format": "json",
        "stream": False,
    }

    start = time.perf_counter()

    response = requests.post(
        f"{OLLAMA_ENDPOINT}/api/generate",
        json=payload,
        timeout=120,
    )

    response.raise_for_status()

    elapsed = time.perf_counter() - start

    result = response.json()
    print("\n----- Metrics -----")
    print(f"Total Duration : {result['total_duration'] / 1_000_000_000:.2f} sec")
    print(f"Latency        : {elapsed:.2f} sec")
    print("-------------------")

    return result


def ask_llm_with_tool_result(
    original_prompt: str,
    tool_name: str,
    tool_result: str,
) -> dict:
    follow_up_prompt = f"""
The user asked:

{original_prompt}

You selected this tool:

{tool_name}

The tool returned:

{tool_result}

Now provide a concise final answer to the user.
"""

    return ask_llm(follow_up_prompt)


def run_agent(prompt: str) -> str:
    result = ask_llm(prompt)

    decision = parse_decision(result["response"])

    if decision is None:
        return f"Gemma returned invalid JSON: {result['response']}"

    action = decision.get("action")

    if action == "answer":
        return decision.get("answer", "No answer was returned.")

    if action != "tool":
        return f"Unknown action requested: {action}"

    tool_name = decision.get("tool_name")
    arguments = decision.get("arguments") or {}

    tool_function = TOOLS.get(tool_name)

    if tool_function is None:
        return f"Unsupported tool requested: {tool_name}"

    tool_result = tool_function(arguments)

    final_result = ask_llm_with_tool_result(
        original_prompt=prompt,
        tool_name=tool_name,
        tool_result=tool_result,
    )

    return extract_answer(final_result["response"])


def main():
    print("Type 'exit' to stop.\n")

    while True:
        prompt = input("You: ").strip()

        if prompt.lower() == "exit":
            print("Goodbye.")
            break

        if not prompt:
            continue

        answer = run_agent(prompt)

        print(f"\nAgent:\n{answer}")
        print("-" * 40)


if __name__ == "__main__":
    main()
