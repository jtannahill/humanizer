"""Ollama provider helpers.

Lets the rewrite endpoints route to a local Ollama model on Apple Silicon
instead of the Anthropic API. Models are addressed with an `ollama:` prefix
(e.g. `ollama:llama3.1:8b`); everything else is treated as a Claude model and
handled by the anthropic SDK upstream.

Pure helpers here (routing, payload shape, parsing) carry no network or Flask
dependency so they stay unit-testable. The thin HTTP wrappers at the bottom
talk to a local Ollama server (default http://localhost:11434).
"""

import json
import os

import requests

OLLAMA_PREFIX = "ollama:"
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
TEMPERATURE = 1.0


OUTPUT_GUARD = (
    "\n\nOUTPUT CONTRACT: Reply with ONLY the rewritten text. No preamble, "
    "no explanations, no headings, no labels, no lists, no commentary about "
    "what you changed."
)


def with_output_guard(user: str, prose_only: bool) -> str:
    """Append a hard no-preamble contract for prose-producing calls.

    Small local models often leak preamble or headings; this reins them in.
    Skipped for non-prose calls (e.g. the nuclear fact-extraction step, which
    must return a bullet list).
    """
    if prose_only:
        return user + OUTPUT_GUARD
    return user


def is_ollama_model(model: str) -> bool:
    """True when the model string targets a local Ollama model."""
    return bool(model) and model.startswith(OLLAMA_PREFIX)


def ollama_model_name(model: str) -> str:
    """Strip the leading `ollama:` route prefix, preserving any tag colon."""
    if is_ollama_model(model):
        return model[len(OLLAMA_PREFIX):]
    return model


def build_ollama_payload(model, system, user, max_tokens, stream):
    """Build an Ollama /api/chat request body from a system+user prompt."""
    return {
        "model": ollama_model_name(model),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": stream,
        "options": {
            "temperature": TEMPERATURE,
            "num_predict": max_tokens,
        },
    }


def parse_ollama_stream_line(line: str) -> str:
    """Extract the content delta from one NDJSON line of a streamed response.

    Returns '' for blank lines, the done marker, or any line without content.
    """
    if not line or not line.strip():
        return ""
    obj = json.loads(line)
    return (obj.get("message") or {}).get("content", "") or ""


def parse_ollama_response(obj: dict) -> str:
    """Pull the full assistant text out of a non-streamed /api/chat response."""
    return (obj.get("message") or {}).get("content", "") or ""


# --- HTTP wrappers (network; not unit-tested) ---

def ollama_chat(model, system, user, max_tokens, timeout=300):
    """Blocking call: return the full assistant text."""
    payload = build_ollama_payload(model, system, user, max_tokens, stream=False)
    resp = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=timeout)
    resp.raise_for_status()
    return parse_ollama_response(resp.json())


def ollama_chat_stream(model, system, user, max_tokens, timeout=300):
    """Generator: yield assistant text chunks as they arrive."""
    payload = build_ollama_payload(model, system, user, max_tokens, stream=True)
    with requests.post(
        f"{OLLAMA_HOST}/api/chat", json=payload, stream=True, timeout=timeout
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            chunk = parse_ollama_stream_line(line)
            if chunk:
                yield chunk


def list_ollama_models(timeout=3):
    """Return the names of locally pulled Ollama models (empty if unreachable)."""
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=timeout)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []
