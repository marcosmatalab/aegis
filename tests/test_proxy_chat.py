"""Non-streaming POST /v1/chat/completions contract (OpenAI response shape)."""

from __future__ import annotations


def test_returns_200_and_openai_shape(client, chat_payload):
    resp = client.post("/v1/chat/completions", json=chat_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["id"], str) and body["id"].startswith("chatcmpl-")
    assert body["object"] == "chat.completion"
    assert isinstance(body["created"], int) and body["created"] > 0
    assert body["model"] == "mock/echo-1"

    choice = body["choices"][0]
    assert choice["index"] == 0
    assert choice["message"]["role"] == "assistant"
    assert isinstance(choice["message"]["content"], str) and choice["message"]["content"]
    assert choice["finish_reason"] == "stop"

    usage = body["usage"]
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]


def test_system_fingerprint_omitted_when_absent(client, chat_payload):
    body = client.post("/v1/chat/completions", json=chat_payload()).json()
    assert "system_fingerprint" not in body  # exclude_none drops unset optionals


def test_model_string_passthrough_echoed(client, chat_payload):
    body = client.post("/v1/chat/completions", json=chat_payload(model="foo/bar-9")).json()
    assert body["model"] == "foo/bar-9"


def test_multi_message_conversation(client, chat_payload):
    payload = chat_payload(
        messages=[
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "bye"},
        ]
    )
    body = client.post("/v1/chat/completions", json=payload).json()
    assert len(body["choices"]) == 1
    assert body["choices"][0]["finish_reason"] == "stop"


def test_deterministic_across_identical_requests(client, chat_payload):
    payload = chat_payload()
    a = client.post("/v1/chat/completions", json=payload).json()
    b = client.post("/v1/chat/completions", json=payload).json()
    assert a["id"] == b["id"]
    assert a["created"] == b["created"]
    assert a["choices"][0]["message"]["content"] == b["choices"][0]["message"]["content"]


def test_n_greater_than_one_still_returns_one_choice(client, chat_payload):
    # Documented F1 behavior: the mock ignores n and always returns one choice.
    body = client.post("/v1/chat/completions", json=chat_payload(n=2)).json()
    assert len(body["choices"]) == 1
