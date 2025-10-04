from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from app.backend.apify_client import ApifyClient, ApifyError, get_apify_client
from app.core.config import PlatformLiteral, get_settings

logger = logging.getLogger(__name__)


class TrendService:
    def __init__(self, apify_client: ApifyClient | None = None) -> None:
        self.settings = get_settings()
        self.apify_client = apify_client or get_apify_client()

    def fetch_trends(self, platform: PlatformLiteral, limit: int = 5) -> Tuple[str, Dict[str, Any]]:
        """Fetch a summary string for the requested platform."""

        actor_id = self._actor_for_platform(platform)
        payload = self._payload_for_platform(platform)

        try:
            summary = self.apify_client.run_actor(
                actor_id,
                payload,
                timeout_sec=self.settings.apify_default_timeout_sec,
            )
        except ApifyError as exc:
            logger.error("Apify error for platform %s: %s", platform, exc)
            raise

        debug: Dict[str, Any] = {
            "actor_id": actor_id,
            "input": payload,
            "limit": limit,
        }
        return summary, debug

    def _actor_for_platform(self, platform: PlatformLiteral) -> str:
        mapping = {
            "tiktok": self.settings.apify_tiktok_actor,
            "x": self.settings.apify_x_actor,
            "facebook": self.settings.apify_facebook_actor,
        }
        return mapping[platform]

    def _payload_for_platform(self, platform: PlatformLiteral) -> Dict[str, Any]:
        if platform == "tiktok":
            return {
                "proxyConfiguration": {
                    "useApifyProxy": False,
                    "apifyProxyGroups": [],
                },
                "countryCode": "US",
                "period": "7",
                "maxItems": 25,
            }
        # Facebook uses the same default input shape as the X snippet per requirements.
        return {
            "country": "2",
            "live": True,
            "hour1": False,
            "hour3": False,
            "hour6": False,
            "hour12": False,
            "hour24": False,
            "day2": False,
            "day3": False,
            "proxyOptions": {"useApifyProxy": True},
        }