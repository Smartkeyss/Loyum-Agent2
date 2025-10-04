from __future__ import annotations

from typing import Any, Dict, List

import pytest
pytest.importorskip("pydantic")
pytest.importorskip("httpx")

from app.backend.services.trends_service import TrendService


class DummyApifyClient:
    def __init__(self, payload: List[Dict[str, Any]]) -> None:
        self.payload = payload

    def run_actor(self, actor_id: str, input_payload: Dict[str, Any], timeout_sec: int | None = None):
        return self.payload


def _ensure_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("APIFY_TOKEN", "test")
    monkeypatch.setenv("APIFY_TIKTOK_ACTOR", "actor/tiktok")
    monkeypatch.setenv("APIFY_X_ACTOR", "actor/x")
    monkeypatch.setenv("APIFY_FACEBOOK_ACTOR", "actor/facebook")


@pytest.mark.parametrize(
    "platform,payload",
    [
        (
            "tiktok",
            [
                {"aweme_id": "123", "desc": "Cool dance", "share_url": "https://tiktok.com/123", "playCount": 1000, "diggCount": 50, "shareCount": 10},
            ],
        ),
        (
            "x",
            [
                {"id": "trend1", "name": "#AI", "url": "https://x.com/hashtag/AI", "tweet_volume": 5000, "retweets": 200},
            ],
        ),
        (
            "facebook",
            [
                {"id": "fb1", "title": "Community Cleanup", "link": "https://facebook.com/post/1", "views": 2000, "likes": 300, "shares": 40},
            ],
        ),
    ],
)
def test_trend_normalization(monkeypatch: pytest.MonkeyPatch, platform: str, payload: List[Dict[str, Any]]) -> None:
    _ensure_env(monkeypatch)
    service = TrendService(apify_client=DummyApifyClient(payload))
    trends, raw = service.fetch_trends(platform, limit=5)
    assert len(trends) == len(payload)
    trend = trends[0]
    assert trend.id
    assert trend.title
    assert trend.metrics is not None
    assert isinstance(trend.raw, dict)
    assert raw == payload