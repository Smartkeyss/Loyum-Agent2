from __future__ import annotations

import os
from typing import Dict, List, Tuple

import httpx
import streamlit as st

from app.backend.schemas import Idea, IdeasRequest, IdeasResponse, Post, PostsRequest, PostsResponse, Trend, TrendRequest, TrendsResponse
from app.frontend import components
from app.frontend.state import SessionState
import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))

BACKEND_URL = os.getenv("BACKEND_URL", f"http://localhost:{os.getenv('BACKEND_PORT', '8000')}")


def get_state() -> SessionState:
    if "app_state" not in st.session_state:
        st.session_state.app_state = SessionState()
    return st.session_state.app_state


def get_cache() -> Dict[str, Dict[str, object]]:
    if "platform_cache" not in st.session_state:
        st.session_state.platform_cache = {}
    return st.session_state.platform_cache


def reset_for_platform(state: SessionState, platform: str) -> None:
    state.platform = platform
    state.selected_trend = None
    state.selected_idea = None
    state.posts = None
    cache = get_cache().setdefault(platform, {"trends": None, "ideas": {}, "posts": {}})
    if cache.get("trends"):
        state.trends = cache["trends"]  # type: ignore[assignment]
    else:
        state.trends = None
    state.ideas = None


def fetch_trends(state: SessionState, platform: str, force: bool = False) -> None:
    cache = get_cache().setdefault(platform, {"trends": None, "ideas": {}, "posts": {}})
    if not force and cache.get("trends"):
        state.trends = cache["trends"]  # type: ignore[assignment]
        state.last_trends_debug = cache.get("trends_debug", {})  # type: ignore[assignment]
        return

    try:
        response = httpx.post(
            f"{BACKEND_URL}/trends/fetch",
            json=TrendRequest(platform=platform, limit=5).model_dump(),
            timeout=30,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        st.error(f"Failed to fetch trends: {exc}")
        return

    payload = response.json()
    data = TrendsResponse.model_validate(payload)
    state.trends = data.trends
    state.last_trends_debug = data.debug or {}
    cache["trends"] = data.trends
    cache["trends_debug"] = state.last_trends_debug
    cache["ideas"] = cache.get("ideas", {})
    cache["posts"] = cache.get("posts", {})
    if not data.trends:
        st.info("No trends returned—try again.")


def generate_ideas(state: SessionState, platform: str, trend: Trend, force: bool = False) -> None:
    cache = get_cache().setdefault(platform, {"trends": None, "ideas": {}, "posts": {}})
    ideas_cache: Dict[str, List[Idea]] = cache.setdefault("ideas", {})  # type: ignore[assignment]
    debug_cache: Dict[str, Dict[str, object]] = cache.setdefault("ideas_debug", {})  # type: ignore[assignment]
    if not force and trend.id in ideas_cache:
        state.ideas = ideas_cache[trend.id]
        state.last_ideas_debug = debug_cache.get(trend.id, {})
        return

    try:
        request = IdeasRequest(platform=platform, trend=trend)
        response = httpx.post(f"{BACKEND_URL}/ideas/generate", json=request.model_dump(), timeout=60)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        st.error(f"Failed to generate ideas: {exc}")
        return

    payload = response.json()
    data = IdeasResponse.model_validate(payload)
    state.ideas = data.ideas
    state.last_ideas_debug = data.debug or {}
    ideas_cache[trend.id] = data.ideas
    debug_cache[trend.id] = state.last_ideas_debug
    if not data.ideas:
        st.info("No ideas generated—try again.")


def generate_posts(state: SessionState, platform: str, idea: Idea, force: bool = False) -> None:
    cache = get_cache().setdefault(platform, {"trends": None, "ideas": {}, "posts": {}})
    posts_cache: Dict[Tuple[str, str], List[Post]] = cache.setdefault("posts", {})  # type: ignore[assignment]
    debug_cache: Dict[Tuple[str, str], Dict[str, object]] = cache.setdefault("posts_debug", {})  # type: ignore[assignment]
    key = (state.selected_trend.id if state.selected_trend else idea.id, idea.id)
    if not force and key in posts_cache:
        state.posts = posts_cache[key]
        state.last_posts_debug = debug_cache.get(key, {})
        return

    try:
        request = PostsRequest(platform=platform, idea=idea, count=3)
        response = httpx.post(f"{BACKEND_URL}/posts/generate", json=request.model_dump(), timeout=60)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        st.error(f"Failed to generate posts: {exc}")
        return

    payload = response.json()
    data = PostsResponse.model_validate(payload)
    state.posts = data.posts
    state.last_posts_debug = data.debug or {}
    posts_cache[key] = data.posts
    debug_cache[key] = state.last_posts_debug
    if not data.posts:
        st.info("No posts generated—try again.")


def main() -> None:
    st.set_page_config(page_title="Trend Agents", layout="wide")
    state = get_state()
    get_cache()

    st.sidebar.title("Control Center")
    platform = st.sidebar.selectbox("Platform", ["TikTok", "X", "Facebook"], index=0)
    normalized_platform = platform.lower()
    if state.platform != normalized_platform:
        reset_for_platform(state, normalized_platform)

    fetch_clicked = st.sidebar.button("Fetch Top 5 Trends")
    regenerate_clicked = st.sidebar.button("Regenerate Trends")
    debug_enabled = st.sidebar.toggle("Show debug payloads", value=state.debug_enabled)
    state.debug_enabled = debug_enabled

    if fetch_clicked:
        fetch_trends(state, normalized_platform)
    elif regenerate_clicked:
        fetch_trends(state, normalized_platform, force=True)

    if state.trends is None:
        st.info("Choose a platform and fetch trends to begin.")
        return

    if state.selected_trend and state.selected_idea and state.posts:
        st.header("Generated Posts")
        components.render_post_cards(state.posts)
        cols = st.columns(3)
        if cols[0].button("Back to Ideas"):
            state.posts = None
        if cols[1].button("Regenerate Posts"):
            generate_posts(state, normalized_platform, state.selected_idea, force=True)
        if cols[2].button("Back to Trends"):
            state.selected_idea = None
            state.ideas = None
            state.posts = None
        if state.debug_enabled and state.last_posts_debug:
            components.render_debug_payload("Last OpenAI posts prompt", state.last_posts_debug)
        return

    if state.selected_trend:
        if state.ideas is None:
            generate_ideas(state, normalized_platform, state.selected_trend)
        st.header("Ideas")
        components.render_idea_cards(state.ideas or [], lambda idea: select_idea(state, normalized_platform, idea))
        cols = st.columns(3)
        if cols[0].button("Back to Trends"):
            state.selected_trend = None
            state.ideas = None
            state.selected_idea = None
            state.posts = None
        if cols[1].button("Regenerate Ideas"):
            generate_ideas(state, normalized_platform, state.selected_trend, force=True)
        if state.debug_enabled and state.last_ideas_debug:
            components.render_debug_payload("Last OpenAI ideas prompt", state.last_ideas_debug)
        if state.selected_idea and state.posts:
            components.render_post_cards(state.posts)
        return

    st.header("Top Trends")

    def on_select(trend: Trend) -> None:
        state.selected_trend = trend
        state.selected_idea = None
        state.posts = None
        generate_ideas(state, normalized_platform, trend)

    components.render_trend_cards(state.trends, on_select)

    if state.debug_enabled and state.last_trends_debug:
        components.render_debug_payload("Last Apify payload", state.last_trends_debug)


def select_idea(state: SessionState, platform: str, idea: Idea) -> None:
    state.selected_idea = idea
    generate_posts(state, platform, idea)


if __name__ == "__main__":
    main()