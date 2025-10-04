from __future__ import annotations

from typing import Any, Dict, List

import pytest
pytest.importorskip("pydantic")
pytest.importorskip("httpx")

from app.backend.services.trends_service import TrendService


class DummyApifyClient:
    def __init__(self, payload: str) -> None:
        self.payload = payload

    def run_actor(
        self, actor_id: str, input_payload: Dict[str, Any], timeout_sec: int | None = None
    ) -> str:
        return self.payload


def _ensure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("APIFY_TOKEN", "test")
    monkeypatch.setenv("APIFY_TIKTOK_ACTOR", "actor/tiktok")
    monkeypatch.setenv("APIFY_X_ACTOR", "actor/x")
    monkeypatch.setenv("APIFY_FACEBOOK_ACTOR", "actor/facebook")


@pytest.mark.parametrize(
    "platform,summary",
    [
        ("tiktok", "1. Dance Challenge — 2,500,000"),
        ("x", "1. #AI — 120,000"),
        ("facebook", "1. Community Cleanup — 5,000"),
    ],
)
def test_trend_summary(monkeypatch: pytest.MonkeyPatch, platform: str, summary: str) -> None:
    _ensure_env(monkeypatch)
    service = TrendService(apify_client=DummyApifyClient(summary))
    result_summary, debug_payload = service.fetch_trends(platform, limit=5)
    assert result_summary == summary
    assert "actor_id" in debug_payload
    assert "input" in debug_payload