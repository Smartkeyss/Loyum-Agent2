from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from app.backend.apify_client import ApifyClient, ApifyError, get_apify_client
from app.backend.schemas import Trend, TrendMetrics
from app.core.config import PlatformLiteral, get_settings

logger = logging.getLogger(__name__)


class TrendService:
    def __init__(self, apify_client: ApifyClient | None = None) -> None:
        self.settings = get_settings()
        self.apify_client = apify_client or get_apify_client()

    def fetch_trends(self, platform: PlatformLiteral, limit: int = 5) -> Tuple[List[Trend], List[Dict[str, Any]]]:
        actor_id = self._actor_for_platform(platform)
        adapter = self._adapter_for_platform(platform)

        payload = {"limit": limit}
        try:
            items = self.apify_client.run_actor(actor_id, payload, timeout_sec=self.settings.apify_default_timeout_sec)
        except ApifyError as exc:
            logger.error("Apify error for platform %s: %s", platform, exc)
            raise

        if not isinstance(items, list):
            logger.warning("Unexpected Apify response type for platform %s: %s", platform, type(items))
            raise ApifyError("Apify actor returned unexpected payload")

        normalized: List[Trend] = []
        for raw in items[:limit]:
            normalized.append(adapter(raw))
        if not normalized:
            logger.info("No trends returned for platform %s", platform)
        return normalized, items

    def _actor_for_platform(self, platform: PlatformLiteral) -> str:
        mapping = {
            "tiktok": self.settings.apify_tiktok_actor,
            "x": self.settings.apify_x_actor,
            "facebook": self.settings.apify_facebook_actor,
        }
        return mapping[platform]

    def _adapter_for_platform(self, platform: PlatformLiteral):
        adapters = {
            "tiktok": _normalize_tiktok_trend,
            "x": _normalize_x_trend,
            "facebook": _normalize_facebook_trend,
        }
        return adapters[platform]


def _normalize_tiktok_trend(raw: Dict[str, Any]) -> Trend:
    # TODO: adjust field mappings once final actor schema is known.
    identifier = str(raw.get("id") or raw.get("aweme_id") or raw.get("video_id") or raw.get("url") or hash(str(raw)))
    title = raw.get("title") or raw.get("desc") or raw.get("caption") or "Untitled TikTok trend"
    url = raw.get("url") or raw.get("share_url")
    metrics = TrendMetrics(
        views=_parse_int(raw.get("playCount") or raw.get("views")),
        likes=_parse_int(raw.get("diggCount") or raw.get("likes")),
        shares=_parse_int(raw.get("shareCount") or raw.get("shares")),
    )
    return Trend(id=identifier, title=title, url=url, metrics=metrics, raw=raw)


def _normalize_x_trend(raw: Dict[str, Any]) -> Trend:
    identifier = str(raw.get("id") or raw.get("name") or raw.get("topic") or hash(str(raw)))
    title = raw.get("title") or raw.get("name") or raw.get("topic") or "Untitled X trend"
    url = raw.get("url") or raw.get("link")
    metrics = TrendMetrics(
        views=_parse_int(raw.get("tweet_volume") or raw.get("views")),
        likes=_parse_int(raw.get("likes")),
        shares=_parse_int(raw.get("retweets") or raw.get("quotes")),
    )
    return Trend(id=identifier, title=title, url=url, metrics=metrics, raw=raw)


def _normalize_facebook_trend(raw: Dict[str, Any]) -> Trend:
    identifier = str(raw.get("id") or raw.get("post_id") or raw.get("group_id") or hash(str(raw)))
    title = raw.get("title") or raw.get("name") or raw.get("headline") or "Untitled Facebook trend"
    url = raw.get("url") or raw.get("link")
    metrics = TrendMetrics(
        views=_parse_int(raw.get("views")),
        likes=_parse_int(raw.get("likes")),
        shares=_parse_int(raw.get("shares")),
    )
    return Trend(id=identifier, title=title, url=url, metrics=metrics, raw=raw)


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None