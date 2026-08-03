import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT")
MODEL = os.getenv("MODEL")

if not OLLAMA_ENDPOINT:
    raise RuntimeError("OLLAMA_ENDPOINT is missing from the .env file.")

if not MODEL:
    raise RuntimeError("MODEL is missing from the .env file.")


def ask_llm(prompt: str) -> dict:
    payload = {
        "model": MODEL,
        "prompt": prompt,
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


def main():
    print("Type 'exit' to stop.\n")

    while True:
        prompt = input("You: ").strip()

        if prompt.lower() == "exit":
            print("Goodbye.")
            break

        if not prompt:
            continue

        result = ask_llm(prompt)

        print(f"\nGemma:\n{result['response']}")
        print(f"\nPrompt tokens: {result['prompt_eval_count']}")
        print(f"Output tokens: {result['eval_count']}")
        print("-" * 40)


if __name__ == "__main__":
    main()