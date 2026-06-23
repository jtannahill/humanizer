"""Unit tests for the Ollama provider helpers.

Pure functions only: model routing, request payload shape, and parsing of
both streamed (NDJSON) and non-streamed Ollama responses. No network.
"""

import json

from ollama_client import (
    is_ollama_model,
    ollama_model_name,
    build_ollama_payload,
    parse_ollama_stream_line,
    parse_ollama_response,
    with_output_guard,
    OUTPUT_GUARD,
)


def test_output_guard_appended_when_prose_only():
    out = with_output_guard("Rewrite this.", prose_only=True)
    assert out.startswith("Rewrite this.")
    assert out.endswith(OUTPUT_GUARD)


def test_output_guard_absent_when_not_prose_only():
    # The fact-extraction step needs a bullet list, so it must not be guarded.
    assert with_output_guard("Extract facts.", prose_only=False) == "Extract facts."


def test_is_ollama_model_true_for_prefixed():
    assert is_ollama_model("ollama:llama3.1:8b") is True


def test_is_ollama_model_false_for_claude():
    assert is_ollama_model("claude-opus-4-7") is False


def test_ollama_model_name_strips_prefix_only_once():
    # The tag itself contains a colon (llama3.1:8b); only the leading
    # "ollama:" must be removed.
    assert ollama_model_name("ollama:llama3.1:8b") == "llama3.1:8b"


def test_build_payload_has_system_and_user_messages():
    payload = build_ollama_payload(
        model="ollama:llama3.1:8b",
        system="SYS",
        user="USR",
        max_tokens=4000,
        stream=True,
    )
    assert payload["model"] == "llama3.1:8b"
    assert payload["stream"] is True
    assert payload["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USR"},
    ]


def test_build_payload_maps_temperature_and_token_cap():
    payload = build_ollama_payload(
        model="ollama:qwen2.5", system="S", user="U", max_tokens=16000, stream=False
    )
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == 1.0
    assert payload["options"]["num_predict"] == 16000


def test_parse_stream_line_extracts_content_delta():
    line = json.dumps({"message": {"role": "assistant", "content": "Hel"}, "done": False})
    assert parse_ollama_stream_line(line) == "Hel"


def test_parse_stream_line_returns_empty_for_done_marker():
    line = json.dumps({"message": {"role": "assistant", "content": ""}, "done": True})
    assert parse_ollama_stream_line(line) == ""


def test_parse_stream_line_returns_empty_for_blank():
    assert parse_ollama_stream_line("") == ""
    assert parse_ollama_stream_line("   ") == ""


def test_parse_response_returns_full_message_content():
    obj = {"message": {"role": "assistant", "content": "full text"}, "done": True}
    assert parse_ollama_response(obj) == "full text"
