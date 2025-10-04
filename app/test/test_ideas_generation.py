import pytest
from app.backend.schemas import Idea, IdeasRequest, Trend, TrendMetrics
from app.backend.services.ideas_service import IdeasService

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
    def create(self, **_):
        self.calls += 1
        return MockResponse(self.content)

class MockChat:
    def __init__(self, content: str) -> None:
        self.completions = MockCompletions(content)

class MockOpenAI:
    def __init__(self, content: str) -> None:
        self.chat = MockChat(content)

def json_dumps(payload):
    import json
    return json.dumps(payload)

def _ensure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("APIFY_TOKEN", "test")

def test_generate_ideas(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_env(monkeypatch)
    trend = Trend(id="1", title="AI Dance", url=None, metrics=TrendMetrics(), raw={})
    request = IdeasRequest(platform="tiktok", trend=trend)
    ideas_payload = {"ideas":[{"id":f"idea-{i}","summary":f"Idea {i}","rationale":"Fits platform"} for i in range(1,6)]}
    mock_client = MockOpenAI(content=json_dumps(ideas_payload))
    service = IdeasService(client=mock_client)  # type: ignore[arg-type]
    ideas, debug = service.generate_ideas(request)
    assert len(ideas) == 5
    assert all(isinstance(idea, Idea) for idea in ideas)
    assert all(idea.summary for idea in ideas)
    assert "prompt" in debug
    assert mock_client.chat.completions.calls == 1
