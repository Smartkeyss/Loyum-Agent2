from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import orjson
from openai import APIConnectionError, APIError, OpenAI, RateLimitError, Timeout
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.backend.schemas import Idea, IdeasRequest
from app.core.config import PlatformLiteral, get_settings
from app.core.logging import log_external_call
from app.core.prompts import make_trend_to_ideas_prompt

logger = logging.getLogger(__name__)


class OpenAIJSONError(Exception):
    pass


class IdeasService:
    def __init__(self, client: OpenAI | None = None) -> None:
        self.settings = get_settings()
        self.client = client or OpenAI(api_key=self.settings.openai_api_key)

    def generate_ideas(self, request: IdeasRequest) -> Tuple[List[Idea], Dict[str, Any]]:
        # Pydantic v2: use model_dump() instead of .dict()
        trend_obj: Dict[str, Any] = request.trend.model_dump()
        messages: List[Dict[str, Any]] = make_trend_to_ideas_prompt(request.platform, trend_obj)

        parsed, raw_content = self._call_openai_json(request.platform, messages, root_key="ideas")

        ideas_payload = parsed.get("ideas")
        if not isinstance(ideas_payload, list):
            raise OpenAIJSONError("OpenAI response missing 'ideas' list")

        ideas: List[Idea] = []
        for idx, item in enumerate(ideas_payload, start=1):
            # defend against missing keys
            idea_id = str(item.get("id") or f"idea-{idx}")
            summary = (item.get("summary") or "").strip()
            rationale = (item.get("rationale") or "").strip()
            ideas.append(Idea(id=idea_id, summary=summary, rationale=rationale))

        debug = {"prompt": messages, "raw_response": raw_content}
        return ideas, debug

    @retry(
        retry=retry_if_exception_type((RateLimitError, Timeout, APIError, APIConnectionError)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _create_completion(self, platform: PlatformLiteral, messages: List[Dict[str, Any]]):
        with log_external_call(logger, context=f"openai.ideas:{platform}", payload={"message_count": len(messages)}):
            return self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.7,
            )

    def _call_openai_json(
        self,
        platform: PlatformLiteral,
        messages: List[Dict[str, Any]],
        root_key: str,
    ) -> Tuple[Dict[str, Any], str]:
        response = self._create_completion(platform, messages)
        content = response.choices[0].message.content or "{}"

        try:
            parsed = orjson.loads(content)
        except orjson.JSONDecodeError:
            logger.warning("Failed to parse OpenAI JSON for %s, retrying once", platform)
            response = self._create_completion(platform, messages)
            content = response.choices[0].message.content or "{}"
            try:
                parsed = orjson.loads(content)
            except orjson.JSONDecodeError as exc:  # pragma: no cover
                raise OpenAIJSONError("Failed to parse JSON from OpenAI response") from exc

        if root_key not in parsed:
            raise OpenAIJSONError(f"OpenAI response missing root key '{root_key}'")

        return parsed, content
