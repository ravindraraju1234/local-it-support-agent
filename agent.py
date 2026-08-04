import json
import logging
import os
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from logging_config import configure_logging

load_dotenv()



logger = logging.getLogger(__name__)

OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT")
MODEL = os.getenv("MODEL")

print(f"Loaded Ollama endpoint: {OLLAMA_ENDPOINT}")

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

    logger.info("Calling model %s (prompt length %d)", MODEL, len(prompt))

    start = time.perf_counter()

    try:
        response = requests.post(
            f"{OLLAMA_ENDPOINT}/api/generate",
            json=payload,
            timeout=120,
        )

        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Call to %s failed", OLLAMA_ENDPOINT)
        raise

    elapsed = time.perf_counter() - start

    result = response.json()

    logger.info(
        "Model responded in %.2f sec (model time %.2f sec, %s prompt tokens, %s output tokens)",
        elapsed,
        result.get("total_duration", 0) / 1_000_000_000,
        result.get("prompt_eval_count", "?"),
        result.get("eval_count", "?"),
    )

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
    logger.info("Agent execution started for: %.100s", prompt)

    result = ask_llm(prompt)

    decision = parse_decision(result["response"])

    if decision is None:
        logger.warning("Model returned invalid JSON: %.200s", result["response"])
        return f"Gemma returned invalid JSON: {result['response']}"

    action = decision.get("action")

    logger.info("Model decided action: %s", action)

    if action == "answer":
        logger.info("Agent execution completed without a tool call")
        return decision.get("answer", "No answer was returned.")

    if action != "tool":
        logger.warning("Unknown action requested: %s", action)
        return f"Unknown action requested: {action}"

    tool_name = decision.get("tool_name")
    arguments = decision.get("arguments") or {}

    tool_function = TOOLS.get(tool_name)

    if tool_function is None:
        logger.warning("Unsupported tool requested: %s", tool_name)
        return f"Unsupported tool requested: {tool_name}"

    logger.info("Executing tool %s with arguments %s", tool_name, arguments)

    tool_result = tool_function(arguments)

    logger.info("Tool %s returned: %s", tool_name, tool_result)

    final_result = ask_llm_with_tool_result(
        original_prompt=prompt,
        tool_name=tool_name,
        tool_result=tool_result,
    )

    logger.info("Agent execution completed after tool call")

    return extract_answer(final_result["response"])


def main():
    configure_logging()

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
