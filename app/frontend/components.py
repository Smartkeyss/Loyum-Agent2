from __future__ import annotations

import json
from typing import Callable, Iterable

import streamlit as st

from app.backend.schemas import Idea, Post, Trend


def render_trend_cards(trends: Iterable[Trend], on_select: Callable[[Trend], None]) -> None:
    cols = st.columns(1)
    for trend in trends:
        with cols[0]:
            if st.button(trend.title, key=f"trend-{trend.id}"):
                on_select(trend)
            if trend.url:
                st.caption(f"Link: {trend.url}")
            metrics = trend.metrics
            st.caption(
                f"Views: {metrics.views or '—'} · Likes: {metrics.likes or '—'} · Shares: {metrics.shares or '—'}"
            )
            st.divider()


def render_idea_cards(ideas: Iterable[Idea], on_select: Callable[[Idea], None]) -> None:
    for idea in ideas:
        st.subheader(idea.summary)
        st.write(idea.rationale)
        if st.button("Use this idea", key=f"idea-{idea.id}"):
            on_select(idea)
        st.divider()


def render_post_cards(posts: Iterable[Post]) -> None:
    for idx, post in enumerate(posts, start=1):
        st.markdown(f"### Post {idx}")
        st.write(post.post_text)
        st.markdown("**Visual concept**")
        st.write(post.visual_concept)
        if post.hashtags:
            st.markdown("**Hashtags**: " + " ".join(f"#{tag.lstrip('#')}" for tag in post.hashtags))
        st.divider()


def render_debug_payload(title: str, payload: object) -> None:
    st.markdown(f"#### {title}")
    st.code(json.dumps(payload, indent=2, ensure_ascii=False))