"""Rule-based YouTube metadata generation (fully offline, no promises about rankings or views)."""
from __future__ import annotations

import re
from typing import Any

GENRE_TAGS = {
    "fantasy": ["fantasy story", "epic fantasy", "magic kingdom", "animated story"],
    "romance": ["romance story", "enemies to lovers", "love story", "short romance"],
    "horror": ["horror story", "scary stories", "supernatural", "creepypasta style"],
    "mystery": ["mystery story", "thriller", "suspense story", "detective"],
    "adventure": ["adventure story", "action story", "quest", "cinematic story"],
    "drama": ["emotional story", "drama short", "touching story", "short film"],
    "children": ["bedtime story", "kids story", "children's story", "family friendly"],
    "shortfilm": ["short film", "indie short", "original story", "mini movie"],
}


def _clean(title: str) -> str:
    return re.sub(r"[^a-zA-Z0-9 ]", "", title).strip()


def generate_metadata(project: dict[str, Any], scene_timings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    title = project.get("script", {}).get("title") or project.get("name", "Untitled Story")
    settings = project.get("settings", {})
    genre = settings.get("category", "fantasy")
    logline = project.get("script", {}).get("logline", "")
    scenes = project.get("scenes", [])

    base = _clean(title)
    tone_word = settings.get("tone", "cinematic")
    article = "an" if tone_word[:1].lower() in "aeiou" else "a"
    title_opts = [
        base,
        f"{base} | {article.capitalize()} {tone_word} {GENRE_TAGS.get(genre, ['story'])[0]}",
        f"{base} - {('Shorts' if project.get('timeline', {}).get('aspect') == '9:16' else 'Full Story')} "
        f"({len(scenes)} scenes)",
    ]

    desc_lines = [
        base,
        "",
        logline,
        "",
        "Chapters:",
    ]
    chapters = []
    if scene_timings:
        for t in scene_timings:
            ts = f"{int(t['start'] // 60)}:{int(t['start'] % 60):02d}"
            chapters.append(f"{ts} {t['heading']}")
        desc_lines += chapters
    desc_lines += [
        "",
        "Created with StoryForge AI using original writing, local text-to-speech and locally rendered video.",
        "",
        "AI-ASSISTED / SYNTHETIC CONTENT DISCLOSURE:",
        "This video contains AI-assisted writing, synthetic computer-generated narration and/or "
        "computer-generated imagery. No real people are depicted. In line with YouTube's altered/synthetic "
        "content policy, the creator will toggle the synthetic-content declaration in YouTube's upload tools.",
    ]

    keywords = sorted(set(GENRE_TAGS.get(genre, ["story"]) + [
        w.lower() for w in base.split() if len(w) > 3
    ] + ["story video", "ai story", "original story", "youtube story"]))
    hashtags = ["#" + re.sub(r"\W", "", t) for t in
                GENRE_TAGS.get(genre, ["story"])[:3]] + ["#StoryForgeAI", "#OriginalStory"]

    return {
        "title_options": title_opts,
        "description": "\n".join(desc_lines),
        "keywords": keywords,
        "hashtags": hashtags,
        "chapters": chapters,
        "pinned_comment": (
            f"What should happen to the characters of {base} next? Drop your idea in the comments - "
            f"the next story could be yours. (Disclosure: this video contains AI-assisted/synthetic "
            f"writing, narration and imagery; no real people are depicted.)"
        ),
        "disclaimer": (
            "StoryForge does not guarantee rankings, views, monetization or copyright clearance. "
            "Confirm every asset's license and disclose AI-assisted/synthetic content during upload."
        ),
    }
