from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import orjson
from openai import APIConnectionError, APIError, OpenAI, RateLimitError, Timeout
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.backend.schemas import Idea, Post, PostsRequest
from app.core.config import PlatformLiteral, get_settings
from app.core.logging import log_external_call
from app.core.prompts import make_idea_to_posts_prompt

logger = logging.getLogger(__name__)


class PostsService:
    def __init__(self, client: OpenAI | None = None) -> None:
        self.settings = get_settings()
        self.client = client or OpenAI(api_key=self.settings.openai_api_key)

    def generate_posts(self, request: PostsRequest) -> Tuple[List[Post], Dict[str, Any]]:
        messages = make_idea_to_posts_prompt(request.platform, request.idea.dict())
        parsed, raw_content = self._call_openai_json(request.platform, messages, root_key="posts")
        posts_payload = parsed.get("posts")
        if not isinstance(posts_payload, list):
            raise ValueError("OpenAI response missing 'posts' list")
        posts: List[Post] = []
        for item in posts_payload:
            post_text = item.get("post_text") or ""
            visual_concept = item.get("visual_concept") or ""
            hashtags = item.get("hashtags") or []
            if not isinstance(hashtags, list):
                hashtags = []
            posts.append(Post(post_text=post_text, visual_concept=visual_concept, hashtags=list(map(str, hashtags))))
        debug = {"prompt": messages, "raw_response": raw_content}
        return posts, debug

    @retry(
        retry=retry_if_exception_type((RateLimitError, Timeout, APIError, APIConnectionError)),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _create_completion(self, platform: PlatformLiteral, messages: List[Dict[str, Any]]):
        with log_external_call(logger, context=f"openai.posts:{platform}", payload={"message_count": len(messages)}):
            return self.client.chat.completions.create(
                model=self.settings.openai_model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.8,
            )

    def _call_openai_json(self, platform: PlatformLiteral, messages: List[Dict[str, Any]], root_key: str) -> Tuple[Dict[str, Any], str]:
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
                raise ValueError("Failed to parse JSON from OpenAI response") from exc
        if root_key not in parsed:
            raise ValueError(f"OpenAI response missing root key '{root_key}'")
        return parsed, content