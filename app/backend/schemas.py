from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class TrendMetrics(BaseModel):
    views: Optional[int] = None
    likes: Optional[int] = None
    shares: Optional[int] = None


class Trend(BaseModel):
    id: str
    title: str
    url: Optional[HttpUrl | str] = Field(default=None)
    metrics: TrendMetrics = Field(default_factory=TrendMetrics)
    raw: Dict[str, Any]


class TrendRequest(BaseModel):
    platform: str
    limit: int = 5


class TrendsResponse(BaseModel):
    summary: str
    debug: Optional[Dict[str, Any]] = None


class Idea(BaseModel):
    id: str
    summary: str
    rationale: str


class IdeasRequest(BaseModel):
    platform: str
    trend: Trend


class IdeasResponse(BaseModel):
    ideas: List[Idea]
    debug: Optional[Dict[str, Any]] = None


class Post(BaseModel):
    post_text: str
    visual_concept: str
    hashtags: List[str]


class PostsRequest(BaseModel):
    platform: str
    idea: Idea
    count: int = 3


class PostsResponse(BaseModel):
    posts: List[Post]
    debug: Optional[Dict[str, Any]] = None