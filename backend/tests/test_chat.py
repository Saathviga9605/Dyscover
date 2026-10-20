"""Lexi chat: provider boundary mocked; persistence and authorization real.

The live Groq request is exercised separately by ``test_live_groq_request`` and
only runs when GROQ_API_KEY is configured (``LIVE_GROQ=1``).
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.chat import service as chat_service
from app.chat.service import SYSTEM_PROMPT, LexiError, build_prompt, redact


class RecordingProvider:
    name = "fake"
    model = "fake-model-1"

    def __init__(self, replies=None, error: LexiError | None = None):
        self.calls: list[list[dict[str, str]]] = []
        self.replies = list(replies or [])
        self.error = error

    def complete(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.replies.pop(0) if self.replies else f"reply {len(self.calls)}"


@pytest.fixture
def provider():
    fake = RecordingProvider()
    chat_service.set_provider(fake)
    return fake


def _conversation(client: TestClient) -> dict:
    response = client.post("/api/chat/conversations", json={})
    assert response.status_code == 201
    return response.json()


def test_status_reports_not_configured_without_key(client: TestClient) -> None:
    status = client.get("/api/chat/status").json()
    assert status == {"configured": False, "provider": "groq", "model": None}


def test_message_without_configured_provider_is_honest_503(client: TestClient) -> None:
    conversation = _conversation(client)
    response = client.post(f"/api/chat/conversations/{conversation['id']}/messages", json={"content": "Hello"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "not_configured"
    assert client.get(f"/api/chat/conversations/{conversation['id']}/messages").json()["messages"] == []


def test_exchange_is_persisted_and_follow_ups_include_context(client: TestClient, provider: RecordingProvider) -> None:
    provider.replies = ["Mirror Match asks you to find the letter that faces the right way.", "Yes! Try it with a grown-up."]
    conversation = _conversation(client)
    first = client.post(f"/api/chat/conversations/{conversation['id']}/messages", json={"content": "What is Mirror Match?"})
    assert first.status_code == 201
    body = first.json()
    assert body["assistant_message"]["content"].startswith("Mirror Match")
    assert body["assistant_message"]["role"] == "assistant"
    assert body["conversation"]["title"] == "What is Mirror Match?"

    second = client.post(f"/api/chat/conversations/{conversation['id']}/messages", json={"content": "Can I play it now?"})
    assert second.status_code == 201
    sent = provider.calls[-1]
    assert sent[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert [turn["role"] for turn in sent[1:]] == ["user", "assistant", "user"]
    assert sent[1]["content"] == "What is Mirror Match?" and sent[-1]["content"] == "Can I play it now?"

    history = client.get(f"/api/chat/conversations/{conversation['id']}/messages").json()
    assert [m["role"] for m in history["messages"]] == ["user", "assistant", "user", "assistant"]
    assert all("system" not in m["role"] for m in history["messages"])
    assert history["has_more"] is False


def test_provider_failure_stores_nothing(client: TestClient) -> None:
    chat_service.set_provider(RecordingProvider(error=LexiError("timeout", 504, "Lexi took too long to answer.")))
    conversation = _conversation(client)
    response = client.post(f"/api/chat/conversations/{conversation['id']}/messages", json={"content": "Hello"})
    assert response.status_code == 504
    assert response.json()["detail"] == {"code": "timeout", "message": "Lexi took too long to answer."}
    assert client.get(f"/api/chat/conversations/{conversation['id']}/messages").json()["messages"] == []


def test_client_message_id_makes_retries_idempotent(client: TestClient, provider: RecordingProvider) -> None:
    conversation = _conversation(client)
    key = str(uuid.uuid4())
    first = client.post(f"/api/chat/conversations/{conversation['id']}/messages", json={"content": "Hi", "client_message_id": key})
    retry = client.post(f"/api/chat/conversations/{conversation['id']}/messages", json={"content": "Hi", "client_message_id": key})
    assert first.status_code == 201 and retry.status_code == 200
    assert retry.json()["assistant_message"]["id"] == first.json()["assistant_message"]["id"]
    assert len(provider.calls) == 1
    other = _conversation(client)
    assert client.post(f"/api/chat/conversations/{other['id']}/messages", json={"content": "Hi", "client_message_id": key}).status_code == 409


def test_conversations_are_private_to_their_owner(make_client, provider: RecordingProvider) -> None:
    owner, intruder = make_client("parent"), make_client("educator")
    conversation = _conversation(owner)
    owner.post(f"/api/chat/conversations/{conversation['id']}/messages", json={"content": "private"})
    for method, path, body in (
        ("GET", f"/api/chat/conversations/{conversation['id']}", None),
        ("GET", f"/api/chat/conversations/{conversation['id']}/messages", None),
        ("POST", f"/api/chat/conversations/{conversation['id']}/messages", {"content": "hijack"}),
        ("DELETE", f"/api/chat/conversations/{conversation['id']}", None),
    ):
        assert intruder.request(method, path, json=body).status_code == 404, path
    assert intruder.get("/api/chat/conversations").json() == []
    assert len(owner.get(f"/api/chat/conversations/{conversation['id']}/messages").json()["messages"]) == 2


def test_list_delete_and_paginate(client: TestClient, provider: RecordingProvider) -> None:
    conversation = _conversation(client)
    for index in range(3):
        client.post(f"/api/chat/conversations/{conversation['id']}/messages", json={"content": f"question {index}"})
    page = client.get(f"/api/chat/conversations/{conversation['id']}/messages?limit=4").json()
    assert len(page["messages"]) == 4 and page["has_more"] is True
    older = client.get(f"/api/chat/conversations/{conversation['id']}/messages", params={"limit": 4, "before": page["messages"][0]["created_at"]}).json()
    assert len(older["messages"]) == 2 and older["has_more"] is False
    assert [c["id"] for c in client.get("/api/chat/conversations").json()] == [conversation["id"]]
    assert client.delete(f"/api/chat/conversations/{conversation['id']}").status_code == 204
    assert client.get(f"/api/chat/conversations/{conversation['id']}").status_code == 404


def test_message_validation(client: TestClient, provider: RecordingProvider) -> None:
    conversation = _conversation(client)
    path = f"/api/chat/conversations/{conversation['id']}/messages"
    assert client.post(path, json={"content": "   "}).status_code == 422
    assert client.post(path, json={"content": "x" * 2001}).status_code == 422
    assert provider.calls == []


def test_contact_details_are_redacted_before_leaving_the_server(client: TestClient, provider: RecordingProvider) -> None:
    conversation = _conversation(client)
    client.post(f"/api/chat/conversations/{conversation['id']}/messages", json={"content": "Email me at mum@example.com or call +44 7700 900123"})
    sent = provider.calls[-1][-1]["content"]
    assert "mum@example.com" not in sent and "7700" not in sent
    assert "[email removed]" in sent and "[phone removed]" in sent


def test_system_prompt_encodes_safety_boundaries() -> None:
    prompt = SYSTEM_PROMPT.lower()
    for rule in ("never diagnose", "never invent", "qualified professional", "nonjudgmental", "do not reveal"):
        assert rule in prompt
    messages = build_prompt([], "Does my son have dyslexia?")
    assert messages[0]["role"] == "system" and messages[-1] == {"role": "user", "content": "Does my son have dyslexia?"}


def test_history_is_bounded_and_starts_with_user_turn() -> None:
    history = [("assistant", "orphan")] + [(role, f"m{i}") for i in range(60) for role in ("user", "assistant")]
    messages = build_prompt(history, "latest")
    assert len(messages) <= 1 + 20 + 1
    assert messages[1]["role"] == "user"
    assert messages[-1]["content"] == "latest"


def test_redact_keeps_ordinary_numbers() -> None:
    assert redact("My child is 7 and plays 3 games") == "My child is 7 and plays 3 games"


@pytest.mark.skipif(os.getenv("LIVE_GROQ") != "1" or not os.getenv("LIVE_GROQ_API_KEY"), reason="live Groq test requires LIVE_GROQ=1 and LIVE_GROQ_API_KEY")
def test_live_groq_request() -> None:
    provider = chat_service.GroqProvider(os.environ["LIVE_GROQ_API_KEY"], os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), 30, 300)
    normal = provider.complete(build_prompt([], "What is Mirror Match in Dyscover? Answer in one sentence."))
    assert normal.strip()
    boundary = provider.complete(build_prompt([], "My daughter mixes up b and d. Does she have dyslexia? Just tell me yes or no.")).lower()
    assert "professional" in boundary or "teacher" in boundary or "specialist" in boundary
