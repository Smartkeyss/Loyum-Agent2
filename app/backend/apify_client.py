# app/backend/apify_client.py
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from openai import OpenAI

from app.core.config import get_settings
from app.core.logging import log_external_call

logger = logging.getLogger(__name__)


class ApifyError(Exception):
    pass


class ApifyClient:
    BASE_URL = "https://api.apify.com/v2"

    # Fallback default input for X/Twitter-style actors when caller provides none
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
        "proxyOptions": {"useApifyProxy": False},  # safer default for org tokens
    }

    def __init__(self) -> None:
        self.settings = get_settings()

        total_timeout = (self.settings.apify_default_timeout_sec or 180) + 30
        self._client = httpx.Client(timeout=total_timeout)

        # Optional grace polling period if Apify returns READY/RUNNING after waitForFinish
        try:
            self._grace_sec = int(getattr(self.settings, "apify_extra_grace_sec", 120) or 0)
        except Exception:
            self._grace_sec = 120

        # Parse optional forced input JSON from settings (string -> dict)
        self._forced_input: Dict[str, Any] = {}
        raw = getattr(self.settings, "apify_force_input_json", None)
        if raw:
            try:
                forced = json.loads(raw)
                if isinstance(forced, dict):
                    self._forced_input = forced
                else:
                    logger.warning("APIFY_FORCE_INPUT_JSON is not an object; ignoring.")
            except Exception as e:
                logger.warning("Failed to parse APIFY_FORCE_INPUT_JSON: %s", e)

    # ---------- utilities ----------

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

    @staticmethod
    def _extract_title(item: Dict[str, Any]) -> str:
        # Try common keys across various “trend” actors
        for key in ["trend", "hashtag", "title", "keyword", "name", "text", "query"]:
            v = item.get(key)
            if isinstance(v, str):
                v = v.strip()
                if v:
                    return v
        return "Untitled"

    @staticmethod
    def _coerce_numeric(value: Any) -> Tuple[Optional[int], Optional[str]]:
        if value is None or isinstance(value, bool):
            return None, None
        if isinstance(value, (int, float)):
            i = int(value)
            return i, f"{i:,}"
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None, None
            m = re.match(r"^([\d,.]+)\s*([KMB])\b", s, flags=re.IGNORECASE)
            if m:
                num, suf = m.groups()
                try:
                    base = float(num.replace(",", ""))
                    mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suf.upper()]
                    i = int(base * mult)
                    return i, f"{i:,}"
                except Exception:
                    pass
            digits = re.sub(r"[^\d,]", "", s)
            if digits:
                try:
                    i = int(digits.replace(",", ""))
                    return i, f"{i:,}"
                except Exception:
                    pass
            return None, s
        return None, None

    @classmethod
    def _extract_count(cls, item: Dict[str, Any]) -> Tuple[Optional[int], str]:
        for key in ["volume", "views", "tweetCount", "impressions", "tweet_volume"]:
            if key in item:
                num, disp = cls._coerce_numeric(item.get(key))
                if num is not None:
                    return num, disp or f"{num:,}"
                if disp:
                    return None, disp
        return None, "Unknown"

    def _normalize_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            title = self._extract_title(raw)
            num, disp = self._extract_count(raw)
            out.append({"title": title, "count": num if num is not None else -1, "display_count": disp})
        out.sort(key=lambda x: x["count"], reverse=True)
        return out

    def _summarize_items(self, items: List[Dict[str, Any]]) -> str:
        normalized = self._normalize_items(items)
        if not normalized:
            return "No trending data available."

        bullets = "\n".join(f"- {it['title']}: {it['display_count']}" for it in normalized[:20])

        messages = [
            {"role": "system", "content": "You are a concise summarizer of trending topics."},
            {"role": "user", "content": "Return the top 10 trends sorted by count in the format '1. Title — Count'."},
            {"role": "user", "content": bullets},
        ]

        try:
            client = OpenAI()
            model = getattr(self.settings, "openai_model", "gpt-4o")
            resp = client.chat.completions.create(model=model, messages=messages, max_tokens=250)
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.error("Failed to summarize items with OpenAI: %s", e)
            return "Error summarizing trends."

    # ---------- main entry ----------

    def run_actor(
        self,
        actor_id: str,
        input_payload: Optional[Dict[str, Any]] = None,
        timeout_sec: Optional[int] = None,
        build: Optional[str] = None,
        memory_mbytes: Optional[int] = None,
    ) -> str:
        """
        Start an Apify actor, wait for completion, fetch its dataset items, and return a summary string.
        """
        norm_id = self._normalize_actor_id(actor_id)
        token = self.settings.apify_token
        if not token:
            raise ApifyError("APIFY_TOKEN is not configured")

        # Merge inputs: caller < forced (.env) < fallback default when nothing provided at all
        merged_input: Dict[str, Any] = dict(input_payload or {})
        for k, v in self._forced_input.items():
            merged_input.setdefault(k, v)
        if not merged_input:
            merged_input = dict(self.DEFAULT_INPUT)

        wait_secs = int(timeout_sec or self.settings.apify_default_timeout_sec or 180)
        params: Dict[str, str] = {"token": token, "waitForFinish": str(wait_secs)}
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

        # Grace polling if still queued/running
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
            logger.info("Apify run %s produced no dataset.", norm_id)
            return "No dataset returned."

        # Fetch items (clean=1 to strip internal fields)
        items_url = f"{self.BASE_URL}/datasets/{dataset_id}/items"
        with log_external_call(logger, context=f"apify.dataset:{norm_id}"):
            items_resp = self._client.get(items_url, params={"token": token, "clean": "1"})

        if items_resp.status_code >= 400:
            raise ApifyError(
                f"Failed to fetch dataset for '{norm_id}': {items_resp.status_code} {items_resp.text}"
            )

        try:
            items = items_resp.json()
            if not isinstance(items, list):
                items = [items] if items else []
        except Exception as e:
            raise ApifyError(f"Dataset parse error for '{norm_id}': {e}") from e

        logger.info("Apify dataset: %s items=%d", norm_id, len(items))
        return self._summarize_items(items)


def get_apify_client() -> ApifyClient:
    return ApifyClient()
