from __future__ import annotations

from typing import Any, Dict, List

from .config import PlatformLiteral


def make_style_guidance(platform: PlatformLiteral) -> str:
    guidance = {
        "tiktok": (
            "TikTok style: 15-45s energetic videos, leverage trending sounds, quick cuts, captions on-screen. "
            "Encourage hooks in first 2 seconds and mention duet/stitch options when relevant."
        ),
        "x": (
            "X style: concise 1-2 sentence posts under 260 characters, leverage threads, quotes, and topical hashtags. "
            "Assume casual yet authoritative tone."
        ),
        "facebook": (
            "Facebook style: mix of short paragraphs, emojis sparingly, refer to groups/events/pages. "
            "Highlight community interaction and call-to-action for comments or shares."
        ),
    }
    return guidance[platform]


def make_trend_to_ideas_prompt(platform: PlatformLiteral, trend: Dict[str, Any]) -> List[Dict[str, str]]:
    style = make_style_guidance(platform)
    metrics = trend.get("metrics") or {}
    metrics_summary = ", ".join(f"{k}: {v}" for k, v in metrics.items() if v is not None) or "no metrics provided"
    trend_title = trend.get("title") or "Unknown trend"

    user_content = (
        f"Platform: {platform}. Trend title: {trend_title}. Metrics: {metrics_summary}. "
        "Return exactly 5 ideas in JSON array format under key 'ideas'. Each idea must include 'id', 'summary', and 'rationale'. "
        "Follow platform conventions and stay within brand-safe territory."
    )

    return [
        {
            "role": "system",
            "content": (
                "You are a senior social strategist. Output strictly valid JSON per the provided schema. "
                "Avoid ambiguous language. Reject or reframe disallowed content per policy."
            ),
        },
        {
            "role": "developer",
            "content": (
                "Given a trend title and minimal context, create 5 distinct, creative post ideas tailored to the platform. "
                "Each idea should have a one-sentence summary and a short rationale that references known platform conventions "
                "(e.g., sounds/duets/cuts for TikTok; threads/quotes for X; groups/pages/reels for Facebook). Avoid brand-unsafe topics. "
                f"Style guidance: {style}"
            ),
        },
        {"role": "user", "content": user_content},
    ]


def make_idea_to_posts_prompt(platform: PlatformLiteral, idea: Dict[str, Any]) -> List[Dict[str, str]]:
    style = make_style_guidance(platform)
    idea_summary = idea.get("summary") or "Unknown idea"

    user_content = (
        f"Platform: {platform}. Idea summary: {idea_summary}. Generate exactly 3 posts in JSON under key 'posts'. "
        "Each post needs 'post_text', 'visual_concept', and 'hashtags' (list of 5-8 items). Ensure copy is platform-appropriate and safe."
    )

    return [
        {
            "role": "system",
            "content": (
                "You are an expert copywriter and concept developer. Output strictly valid JSON per the provided schema. "
                "Avoid ambiguous wording. Comply with all safety policies."
            ),
        },
        {
            "role": "developer",
            "content": (
                "Generate 3 complete, publish-ready posts for the specified platform. Each post must include: post_text, "
                "visual_concept (a short scene plan suitable for either a single image or a 10–30s video), and 5–8 platform-appropriate hashtags. "
                "Follow platform length and tone norms. Be original; do not reuse the same concept. "
                f"Style guidance: {style}"
            ),
        },
        {"role": "user", "content": user_content},
    ]