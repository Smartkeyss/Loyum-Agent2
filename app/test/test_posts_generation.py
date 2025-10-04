from __future__ import annotations

from typing import Any, Dict

import pytest
pytest.importorskip("pydantic")
pytest.importorskip("httpx")

from app.backend.schemas import Idea, PostsRequest
from app.backend.services.posts_service import PostsService


class MockMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class MockChoice:
    def __init__(self, content: str) -> None:
        self.message = MockMessage(content)


class MockResponse:
    def __init__(self, content: str) -> None:
        self.choices = [MockChoice(content)]


class MockCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    def create(self, **_: Dict[str, Any]) -> MockResponse:
        self.calls += 1
        return MockResponse(self.content)


class MockChat:
    def __init__(self, content: str) -> None:
        self.completions = MockCompletions(content)


class MockOpenAI:
    def __init__(self, content: str) -> None:
        self.chat = MockChat(content)


def _ensure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("APIFY_TOKEN", "test")


def test_generate_posts(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_env(monkeypatch)
    idea = Idea(id="idea-1", summary="Great idea", rationale="")
    request = PostsRequest(platform="x", idea=idea, count=3)
    posts_payload = {
        "posts": [
            {
                "post_text": f"Post {i}",
                "visual_concept": "Scene description",
                "hashtags": [f"tag{i}{j}" for j in range(5, 10)],
            }
            for i in range(1, 4)
        ]
    }
    mock_client = MockOpenAI(content=json_dumps(posts_payload))
    service = PostsService(client=mock_client)  # type: ignore[arg-type]
    posts, debug = service.generate_posts(request)
    assert len(posts) == 3
    for post in posts:
        assert post.post_text
        assert post.visual_concept
        assert 5 <= len(post.hashtags) <= 8
    assert "prompt" in debug
    assert mock_client.chat.completions.calls == 1


def json_dumps(payload: Dict[str, Any]) -> str:
    import json

    return json.dumps(payload)