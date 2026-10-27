"""ASI:One model access for CivicPulse (credentials are injected by Agentverse)."""

import os

from openai import OpenAI, base_url

MODEL_NAME = "asi1"
MAX_TOKENS = 1024



def ask_asi1(messages) -> str | None:
    """Call ASI:One and log the reason if the request fails."""
    api_key = os.environ.get("ASI1_API_KEY")
    base_url = os.environ.get("ASI1_BASE_URL")

    if not api_key:
        print("ASI:One error: ASI1_API_KEY is missing.")
        return None

    if not base_url:
        print("ASI:One error: ASI1_BASE_URL is missing.")
        return None

    try:
        #temp 2 line 
        print("ASI:One credentials detected:", bool(api_key and base_url))
        print("ASI:One endpoint:", base_url)
        client = OpenAI(api_key=api_key, base_url=base_url)

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=MAX_TOKENS,
        )

        content = completion.choices[0].message.content

        if content and content.strip():
            return content.strip()

        print("ASI:One error: The model returned an empty response.")
        return None

    except Exception as exc:
        print(
            f"ASI:One request failed: "
            f"{type(exc).__name__}: {exc}"
        )
        return None
