from openai import OpenAI
from typing import Any
import os
import subprocess

def run_llm(messages):    
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    client_kwargs: dict[str, Any] = {"api_key": api_key}
    client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)

    compression_instruction = (
        "You are compressing an OpenClaw system prompt. "
        "Rewrite it to be under 2000 tokens while preserving behavior. "
        "Keep all critical policy and routing rules: "
        "(1) tool names and their intended usage constraints, "
        "(2) safety and non-delegable prohibitions, "
        "(3) skills-selection rules, "
        "(4) memory recall requirements, "
        "(5) update/config restrictions, "
        "(6) reply-tag/messaging rules, "
        "(7) heartbeat handling rules. "
        "Remove duplicated prose, repeated examples, and decorative language. "
        "Prefer compact bullet sections with short imperative statements. "
        "Do not invent or weaken any rule. "
        "Output only the rewritten system prompt text."
    )
    rewrite_messages = [{"role": "system", "content": compression_instruction}, *messages]

    response = client.chat.completions.create(
        model="gpt-5.2",
        messages=rewrite_messages,
        max_completion_tokens=2500,
    )
    return response.choices[0].message.content


def run_turn(message: str) -> str:
    """Run one OpenClaw agent turn with a user message."""
    cmd = [
        "pnpm", "openclaw", "agent",
        "--message", message,
        "--agent", "main",
    ]
    result = subprocess.run(
        cmd,
        cwd=os.environ.get("OPENCLAW_PATH", ""),
        capture_output=True,
        text=True,
    )
    return result.stdout
