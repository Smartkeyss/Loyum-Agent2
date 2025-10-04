from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.backend.schemas import Idea, Post, Trend


@dataclass
class SessionState:
    platform: Optional[str] = None
    trends: Optional[List[Trend]] = None
    trend_summary: Optional[str] = None
    selected_trend: Optional[Trend] = None
    ideas: Optional[List[Idea]] = None
    selected_idea: Optional[Idea] = None
    posts: Optional[List[Post]] = None
    debug_enabled: bool = False
    last_trends_debug: Dict[str, object] = field(default_factory=dict)
    last_ideas_debug: Dict[str, object] = field(default_factory=dict)
    last_posts_debug: Dict[str, object] = field(default_factory=dict)


DEFAULT_STATE = SessionState()