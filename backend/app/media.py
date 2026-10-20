"""
Local image generation with Pillow: cinematic placeholder frames, title cards and thumbnails.

These are HONESTLY LABELED auto-generated placeholders so the full pipeline works with zero
assets and zero budget. Users replace them with uploaded/licensed images or a connected
local image model (see providers.py).
"""
from __future__ import annotations

import hashlib
import math
import random
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import PROJECTS_DIR

FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"

RESOLUTIONS = {
    # 360p is the fast-preview draft tier (smallest pixel budget on weak free hosts).
    ("16:9", "360p"): (640, 360), ("9:16", "360p"): (360, 640), ("1:1", "360p"): (360, 360),
    ("16:9", "480p"): (854, 480), ("16:9", "720p"): (1280, 720), ("16:9", "1080p"): (1920, 1080),
    ("9:16", "480p"): (480, 854), ("9:16", "720p"): (720, 1280), ("9:16", "1080p"): (1080, 1920),
    ("1:1", "480p"): (480, 480), ("1:1", "720p"): (720, 720), ("1:1", "1080p"): (1080, 1080),
}

# Draft previews trade a little motion smoothness and pixel count for a much faster encode.
PREVIEW_RESOLUTIONS = {"360p", "480p"}
PREVIEW_FPS = 20

# Full-HD frame targets for AI-generated source images (the free image model's native output
# is smaller, so frames are upscaled to these dimensions before they enter the video pipeline).
HD_TARGETS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
}

PALETTE_HEX = {
    "teal and amber": ((14, 38, 48), (214, 142, 64)),
    "indigo with silver": ((18, 20, 52), (196, 204, 220)),
    "ember orange and charcoal": ((32, 22, 24), (226, 110, 52)),
    "forest greens": ((16, 38, 26), (112, 158, 110)),
    "monochrome with a red accent": ((22, 22, 26), (200, 60, 60)),
}


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _gradient(size: tuple[int, int], c1: tuple[int, int, int], c2: tuple[int, int, int],
              vertical: bool = False) -> Image.Image:
    w, h = size
    base = Image.new("RGB", size, c1)
    top = Image.new("RGB", size, c2)
    mask = Image.new("L", size)
    md = mask.load()
    span = h if vertical else w
    for y in range(h):
        for x in range(w):
            t = (y if vertical else x) / max(1, span)
            md[x, y] = int(255 * t)
    base.paste(top, (0, 0), mask)
    return base


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        words = para.split()
        cur = ""
        for word in words:
            trial = (cur + " " + word).strip()
            if draw.textlength(trial, font=font) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def dimensions(aspect: str, resolution: str) -> tuple[int, int]:
    return RESOLUTIONS.get((aspect, resolution), (1280, 720))


def _cinematic_frame(size: tuple[int, int], seed_text: str, palette: str, motif: str) -> Image.Image:
    rng = random.Random(hashlib.md5(seed_text.encode()).hexdigest()[:8])
    colors = next((v for k, v in PALETTE_HEX.items() if palette and palette.split(",")[0] in k),
                  ((16, 20, 34), (96, 120, 170)))
    img = _gradient(size, colors[0], colors[1], vertical=rng.random() > 0.5).filter(ImageFilter.GaussianBlur(2))
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = size
    # soft light orb (moon / sun)
    cx, cy = rng.randint(int(w * 0.2), int(w * 0.8)), rng.randint(int(h * 0.15), int(h * 0.5))
    r = int(min(w, h) * 0.14)
    for i in range(6, 0, -1):
        draw.ellipse((cx - r * i / 2, cy - r * i / 2, cx + r * i / 2, cy + r * i / 2),
                     fill=(255, 245, 220, 14))
    # silhouette horizon
    horizon = int(h * rng.uniform(0.55, 0.75))
    draw.rectangle((0, horizon, w, h), fill=(8, 10, 14, 210))
    # layered procedural hills / ruined towers
    for layer in range(3):
        pts = [(0, h)]
        base_y = horizon + layer * int(h * 0.07)
        x = 0
        while x <= w:
            x += rng.randint(int(w * 0.08), int(w * 0.2))
            pts.append((x, base_y - rng.randint(0, int(h * 0.12))))
        pts += [(w, h), (0, h)]
        draw.polygon(pts, fill=(6, 8, 12, 230 - layer * 40))
    # falling particles (ash / snow / embers)
    for _ in range(int(w * h / 9000)):
        px, py = rng.randint(0, w), rng.randint(0, horizon)
        draw.ellipse((px, py, px + 2, py + 2), fill=(230, 220, 200, rng.randint(60, 160)))
    # letterbox bars to signal cinematic frame
    bar = int(h * 0.06)
    draw.rectangle((0, 0, w, bar), fill=(0, 0, 0, 255))
    draw.rectangle((0, h - bar, w, h), fill=(0, 0, 0, 255))
    return img


def create_placeholder(project_id: str, scene_id: str, prompt: str, style: dict[str, Any],
                       aspect: str = "16:9", resolution: str = "720p", label: str | None = None) -> str:
    w, h = dimensions(aspect, resolution)
    img = _cinematic_frame((w, h), prompt + scene_id, style.get("palette", ""),
                           style.get("effects", "")[:48])
    draw = ImageDraw.Draw(img, "RGBA")
    # Compact, honest label: scene heading + tag (the full visual prompt stays in the editor).
    heading = (label or prompt.split(".")[0])[:90]
    hf = _font(FONT_SERIF, max(24, int(w * 0.034)))
    hlines = _wrap(draw, heading, hf, int(w * 0.84))[:2]
    y = int(h * 0.16)
    for line in hlines:
        tw = draw.textlength(line, font=hf)
        draw.text(((w - tw) / 2 + 2, y + 2), line, font=hf, fill=(0, 0, 0, 190))
        draw.text(((w - tw) / 2, y), line, font=hf, fill=(238, 236, 230, 245))
        y += int(hf.size * 1.2)
    tag = "AUTO PLACEHOLDER - REPLACE WITH YOUR IMAGE OR A CONNECTED LOCAL MODEL"
    tf = _font(FONT_BOLD, max(13, int(w * 0.015)))
    tw = draw.textlength(tag, font=tf)
    draw.rectangle(((w - tw) / 2 - 12, int(h * 0.105), (w + tw) / 2 + 12, int(h * 0.105) + tf.size + 8),
                   fill=(120, 30, 30, 220))
    draw.text(((w - tw) / 2, int(h * 0.105) + 4), tag, font=tf, fill=(255, 235, 235, 255))
    out = PROJECTS_DIR / project_id / "images" / f"placeholder_{scene_id}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return str(out)


def create_title_card(project_id: str, title: str, subtitle: str, aspect: str,
                      resolution: str, kind: str = "intro") -> str:
    w, h = dimensions(aspect, resolution)
    img = _gradient((w, h), (10, 10, 16), (40, 44, 66), vertical=True)
    draw = ImageDraw.Draw(img, "RGBA")
    font = _font(FONT_SERIF, max(34, int(w * 0.06)))
    sub_font = _font(FONT_REG, max(20, int(w * 0.026)))
    lines = _wrap(draw, title, font, int(w * 0.84))
    total = len(lines) * int(font.size * 1.2)
    y = h / 2 - total / 2
    for line in lines:
        tw = draw.textlength(line, font=font)
        draw.text(((w - tw) / 2, y), line, font=font, fill=(240, 236, 226, 255))
        y += int(font.size * 1.2)
    if subtitle:
        for line in _wrap(draw, subtitle, sub_font, int(w * 0.8)):
            tw = draw.textlength(line, font=sub_font)
            draw.text(((w - tw) / 2, y + 18), line, font=sub_font, fill=(185, 190, 205, 255))
            y += int(sub_font.size * 1.2)
    tag = "StoryForge AI" if kind == "outro" else ""
    if tag:
        tf = _font(FONT_REG, int(w * 0.02))
        tw = draw.textlength(tag, font=tf)
        draw.text(((w - tw) / 2, h * 0.88), tag, font=tf, fill=(150, 150, 160, 220))
    out = PROJECTS_DIR / project_id / "images" / f"{kind}_card.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return str(out)


def create_thumbnail(project_id: str, title: str, background: str | None, placement: str,
                     aspect: str = "16:9") -> str:
    w, h = (1280, 720) if aspect == "16:9" else (1080, 1920) if aspect == "9:16" else (1080, 1080)
    if background and Path(background).exists():
        img = Image.open(background).convert("RGB").resize((w, h))
    else:
        img = _cinematic_frame((w, h), title, "indigo with silver", "thumbnail concept")
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # dark band behind text for readability, placement configurable
    font = _font(FONT_BOLD, max(40, int(w * 0.075)))
    lines = _wrap(od, title, font, int(w * 0.88))[:3]
    band_h = len(lines) * int(font.size * 1.15) + 40
    positions = {
        "top": int(h * 0.08), "center": int(h * 0.5 - band_h / 2), "bottom": int(h * 0.78),
    }
    y = positions.get(placement, positions["bottom"])
    od.rectangle((0, y - 20, w, y + band_h), fill=(0, 0, 0, 150))
    for line in lines:
        tw = od.textlength(line, font=font)
        x = (w - tw) / 2
        od.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 255))
        od.text((x, y), line, font=font, fill=(255, 214, 86, 255))
        y += int(font.size * 1.15)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    out = PROJECTS_DIR / project_id / "exports" / "thumbnails" / f"thumb_{abs(hash(title)) % 100000}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return str(out)
