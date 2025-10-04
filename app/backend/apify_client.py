from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx
from openai import OpenAI

from app.core.config import get_settings
from app.core.logging import log_external_call

logger = logging.getLogger(__name__)

# OpenAI client (requires OPENAI_API_KEY in .env)
openai_client = OpenAI()


class ApifyError(Exception):
    pass


class ApifyClient:
    BASE_URL = "https://api.apify.com/v2"

    # Hardcoded default input (from your working API snippet)
    DEFAULT_INPUT: Dict[str, Any] = {
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

    def __init__(self) -> None:
        self.settings = get_settings()
        total_timeout = (self.settings.apify_default_timeout_sec or 180) + 30
        self._client = httpx.Client(timeout=total_timeout)
        try:
            # Optional grace period to poll actor after it starts
            self._grace_sec = int(getattr(self.settings, "apify_extra_grace_sec", 120) or 0)
        except Exception:
            self._grace_sec = 120

    @staticmethod
    def _looks_opaque_actor_id(aid: str) -> bool:
        s = aid.strip()
        if "~" in s or "/" in s:
            return False
        return s.isalnum() and 10 <= len(s) <= 32

    @staticmethod
    def _normalize_actor_id(actor_id: str) -> str:
        aid = actor_id.strip()
        if ApifyClient._looks_opaque_actor_id(aid):
            return aid
        if "~" in aid:
            return aid
        if "/" in aid:
            parts = [p for p in aid.split("/") if p]
            if len(parts) == 2:
                return f"{parts[0]}~{parts[1]}"
        return aid

    def _get_run(self, run_id: str, token: str) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/actor-runs/{run_id}"
        with log_external_call(logger, context=f"apify.run_status:{run_id}"):
            r = self._client.get(url, params={"token": token})
        if r.status_code >= 400:
            raise ApifyError(f"Failed to fetch run '{run_id}': {r.status_code} {r.text}")
        return (r.json() or {}).get("data") or {}

    def _summarize_items(self, items: list[dict]) -> str:
        """Use OpenAI to summarize the dataset items into a concise overview."""
        if not items:
            return "No trending data available."

        # Build a compact input string with top items
        content = "Summarize these trending topics with counts:\n\n"
        for it in items[:20]:  # limit to first 20 for brevity
            title = it.get("trend") or it.get("title") or it.get("hashtag") or "Unknown"
            volume = it.get("volume") or it.get("views") or "N/A"
            content += f"- {title}: {volume}\n"

        try:
            resp = openai_client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {"role": "system", "content": "You are a concise summarizer of trending topics."},
                    {"role": "user", "content": content},
                ],
                max_tokens=250,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Failed to summarize items with OpenAI: %s", e)
            return "Error summarizing trends."

    def run_actor(
        self,
        actor_id: str,
        input_payload: Optional[Dict[str, Any]] = None,
        timeout_sec: Optional[int] = None,
        build: Optional[str] = None,
        memory_mbytes: Optional[int] = None,
    ) -> str:
        """
        Run an Apify actor and return a summary of the dataset items.
        """
        norm_id = self._normalize_actor_id(actor_id)
        token = self.settings.apify_token
        if not token:
            raise ApifyError("APIFY_TOKEN is not configured")

        # Merge with hardcoded defaults (caller overrides specific keys if needed).
        merged_input: Dict[str, Any] = dict(self.DEFAULT_INPUT)
        if input_payload:
            merged_input.update(input_payload)

        wait_secs = int(timeout_sec or self.settings.apify_default_timeout_sec or 180)
        params: Dict[str, str] = {
            "token": token,
            "waitForFinish": str(wait_secs),
        }
        if build:
            params["build"] = build
        if memory_mbytes:
            params["memoryMbytes"] = str(memory_mbytes)

        start_url = f"{self.BASE_URL}/acts/{norm_id}/runs"
        with log_external_call(logger, context=f"apify.run:{norm_id}", payload=merged_input):
            resp = self._client.post(start_url, params=params, json={"input": merged_input})

        if resp.status_code >= 400:
            raise ApifyError(f"Failed to start actor '{norm_id}': {resp.status_code} {resp.text}")

        data = (resp.json() or {}).get("data") or {}
        status = data.get("status")
        run_id = data.get("id")

        if status in {"READY", "RUNNING"} and self._grace_sec > 0 and run_id:
            deadline = time.time() + self._grace_sec
            while time.time() < deadline:
                time.sleep(5)
                data = self._get_run(run_id, token)
                status = data.get("status")
                if status in {"SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"}:
                    break

        if status != "SUCCEEDED":
            raise ApifyError(f"Actor '{norm_id}' finished with status '{status}' (run={run_id})")

        dataset_id = data.get("defaultDatasetId")
        if not dataset_id:
            return "No dataset returned."

        items_url = f"{self.BASE_URL}/datasets/{dataset_id}/items"
        q = {"token": token, "clean": "1"}
        with log_external_call(logger, context=f"apify.dataset:{norm_id}"):
            items_resp = self._client.get(items_url, params=q)

        if items_resp.status_code >= 400:
            raise ApifyError(
                f"Failed to fetch dataset for '{norm_id}': {items_resp.status_code} {items_resp.text}"
            )

        items = items_resp.json()
        if not isinstance(items, list):
            items = [items] if items else []

        # Summarize and return
        summary = self._summarize_items(items)
        logger.info("Apify dataset summary: %s", summary)
        return summary


def get_apify_client() -> ApifyClient:
    return ApifyClient()
