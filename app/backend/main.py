from __future__ import annotations

import logging
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.backend.apify_client import ApifyError
from app.backend.schemas import (
    IdeasRequest,
    IdeasResponse,
    PostsRequest,
    PostsResponse,
    TrendRequest,
    TrendsResponse,
)
from app.backend.services.ideas_service import IdeasService, OpenAIJSONError
from app.backend.services.posts_service import PostsService
from app.backend.services.trends_service import TrendService
from app.core.config import PlatformLiteral, get_settings
from app.core.logging import configure_logging

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(title="Trend Agents Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

trend_service = TrendService()
ideas_service = IdeasService()
posts_service = PostsService()


def _normalize_platform(platform: str) -> PlatformLiteral:
    lowered = platform.lower()
    if lowered not in {"tiktok", "x", "facebook"}:
        raise HTTPException(status_code=400, detail=f"Unsupported platform '{platform}'")
    return lowered  # type: ignore[return-value]


@app.post("/trends/fetch", response_model=TrendsResponse)
def fetch_trends(request: TrendRequest) -> TrendsResponse:
    platform = _normalize_platform(request.platform)
    normalized_request = TrendRequest(platform=platform, limit=request.limit)
    try:
        summary, debug_payload = trend_service.fetch_trends(
            platform, limit=normalized_request.limit
        )
    except ApifyError as exc:
        logger.exception("Trend fetch failed for %s", platform)
        raise HTTPException(status_code=502, detail=str(exc))
    return TrendsResponse(summary=summary, debug=debug_payload)


@app.post("/ideas/generate", response_model=IdeasResponse)
def generate_ideas(request: IdeasRequest) -> IdeasResponse:
    platform = _normalize_platform(request.platform)
    try:
        normalized_request = IdeasRequest(platform=platform, trend=request.trend)
        ideas, debug = ideas_service.generate_ideas(normalized_request)
    except OpenAIJSONError as exc:
        logger.exception("Idea generation parse error for %s", platform)
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:  # pragma: no cover - fallback safety
        logger.exception("Idea generation failed for %s", platform)
        raise HTTPException(status_code=502, detail="Idea generation failed") from exc
    return IdeasResponse(ideas=ideas, debug=debug)


@app.post("/posts/generate", response_model=PostsResponse)
def generate_posts(request: PostsRequest) -> PostsResponse:
    platform = _normalize_platform(request.platform)
    try:
        normalized_request = PostsRequest(platform=platform, idea=request.idea, count=request.count)
        posts, debug = posts_service.generate_posts(normalized_request)
    except Exception as exc:  # pragma: no cover - fallback safety
        logger.exception("Post generation failed for %s", platform)
        raise HTTPException(status_code=502, detail="Post generation failed") from exc
    return PostsResponse(posts=posts, debug=debug)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}