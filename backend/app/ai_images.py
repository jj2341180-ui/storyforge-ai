"""Free, keyless AI text-to-image generation via Pollinations (https://pollinations.ai).

No API key and no paid account are required: Pollinations hosts a free image model and
returns a JPEG for a simple GET request. The anonymous tier is throttled to roughly ONE
image every 45 seconds per IP (HTTP 402 with an explicit retry delay), so this module:

  * serializes requests process-wide and paces them to the documented interval,
  * parses the 402/429 "Retry after Ns" message and waits exactly as long as asked,
  * retries with backoff, and raises a clear error instead of returning a fake image.

Every produced asset is registered by the caller with its source and a license note so
rights stay traceable. Set STORYFORGE_AI_IMAGE_BASE to use a compatible/self-hosted
endpoint, or STORYFORGE_AI_IMAGES=0 to disable the feature.
"""
from __future__ import annotations

import io
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageFilter

from .config import AI_IMAGE_BASE
from .media import HD_TARGETS

USER_AGENT = "StoryForgeAI/1.0 (free local-first story video creator)"
# Anonymous free-tier policy documented by Pollinations (Oct 2026): 1 image / 45s / IP.
MIN_INTERVAL_SECONDS = 46
MAX_RETRY_WAIT = 150
# A neutral cinematic suffix keeps story frames coherent regardless of the user's prompt.
DEFAULT_STYLE_SUFFIX = (
    "cinematic film still, dramatic lighting, detailed scene, depth of field, "
    "no text, no letters, no watermark, no logo"
)

_throttle_lock = threading.Lock()
_last_request_at = 0.0


class RateLimitedError(RuntimeError):
    def __init__(self, retry_after: float):
        super().__init__(f"free image quota reached; retry after {retry_after:.0f}s")
        self.retry_after = retry_after


def _ipv4_only_resolver(original_resolver):
    """Some networks advertise broken IPv6 routes; prefer IPv4 for these downloads."""

    def _resolve(host, *args, **kwargs):
        results = original_resolver(host, *args, **kwargs)
        ipv4 = [r for r in results if r[0] == socket.AF_INET]
        return ipv4 or results

    return _resolve


def _http_get(url: str, timeout: float, throttle: bool = True) -> bytes:
    global _last_request_at
    with _throttle_lock:
        # Respect the per-IP free quota before opening the connection. Retries after a
        # RateLimitedError already slept the server's requested wait, so skip the gate.
        if throttle:
            wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
            if wait > 0:
                time.sleep(wait)
        _last_request_at = time.monotonic()

    original = socket.getaddrinfo
    socket.getaddrinfo = _ipv4_only_resolver(original)
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "image/avif,image/webp,image/*,*/*"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (402, 429):
                retry = _parse_retry_seconds(exc)
                raise RateLimitedError(retry) from exc
            raise
    finally:
        socket.getaddrinfo = original


def _parse_retry_seconds(exc: urllib.error.HTTPError) -> float:
    header = exc.headers.get("Retry-After") if exc.headers else None
    if header and header.isdigit():
        return min(MAX_RETRY_WAIT, float(header) + 1)
    try:
        payload = json.loads(exc.read().decode())
        message = payload.get("error", {}).get("message", "")
        match = re.search(r"Retry after\s+(\d+)\s*s", message)
        if match:
            return min(MAX_RETRY_WAIT, float(match.group(1)) + 1)
    except Exception:
        pass
    return 30.0  # safe default when the server gives no parseable value


def _is_image(blob: bytes) -> bool:
    return blob[:3] == b"\xff\xd8\xff" or blob[:8] == b"\x89PNG\r\n\x1a\n"


def _normalize(blob: bytes, size: tuple[int, int]) -> bytes:
    """Produce a clean HD frame: crop the free-tier logo strip, upscale with high-quality
    resampling, then gently re-sharpen so upscaled detail stays crisp in the video."""
    try:
        img = Image.open(io.BytesIO(blob)).convert("RGB")
        w, h = img.size
        # The anonymous free tier can paint a small provider logo in the bottom-right.
        # Dropping the bottom 8% and resizing back removes it without touching the subject.
        img = img.crop((0, 0, w, int(h * 0.92)))
        if img.size != size:
            img = img.resize(size, Image.LANCZOS)
        # Mild unsharp mask restores perceived detail after the LANCZOS upscale.
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=90, threshold=3))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=92, optimize=True, subsampling=1)
        return buffer.getvalue()
    except Exception:
        return blob


def build_prompt(prompt: str, style: dict | None = None) -> str:
    style = style or {}
    extras = [str(style[k]) for k in ("palette", "effects", "look") if style.get(k)]
    return " ".join([prompt.strip(), *extras, DEFAULT_STYLE_SUFFIX]).strip()


def generate_ai_image(
    prompt: str,
    out_path: str | Path,
    *,
    aspect: str = "16:9",
    resolution: str = "720p",
    seed: int | None = None,
    style: dict | None = None,
    progress_cb=None,
    deadline_seconds: float = 300.0,
) -> dict:
    """Generate one image and write it to out_path.

    Retry policy is time-budgeted rather than attempt-budgeted: quota responses are honored
    until the deadline, so a nearly-open window ("retry after 2s") is never wasted.
    """
    # Always produce a full-HD frame regardless of the export resolution: 720p exports
    # downscale from it (better source detail) and 1080p exports match it 1:1.
    width, height = HD_TARGETS.get(aspect, HD_TARGETS["16:9"])
    seed = int(seed if seed is not None else int(time.time() * 1000) % 1_000_000)
    full_prompt = build_prompt(prompt, style)
    encoded = urllib.parse.quote(full_prompt)[:1800]
    destination = Path(out_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # No "enhance" step: it adds an extra LLM pass and latency; the cinematic suffix is enough.
    url = (
        f"{AI_IMAGE_BASE}/prompt/{encoded}"
        f"?width={width}&height={height}&seed={seed}&nologo=true"
    )

    started = time.monotonic()
    last_error: Exception | None = None
    network_failures = 0
    attempt = 0
    while time.monotonic() - started < deadline_seconds:
        attempt += 1
        try:
            blob = _http_get(url, timeout=150, throttle=attempt == 1)
            if not _is_image(blob):
                raise RuntimeError("the image service returned a non-image response")
            blob = _normalize(blob, (width, height))
            destination.write_bytes(blob)
            return {
                "path": str(destination),
                "seed": seed,
                "width": width,
                "height": height,
                "bytes": len(blob),
                "provider_url": AI_IMAGE_BASE,
                "attempts": attempt,
            }
        except RateLimitedError as exc:
            last_error = exc
            remaining = deadline_seconds - (time.monotonic() - started)
            if remaining <= exc.retry_after:
                break  # not enough time for another full cycle
            if progress_cb:
                progress_cb(f"Free image quota — waiting {exc.retry_after:.0f}s (attempt {attempt})")
            time.sleep(exc.retry_after)
            seed += 1009
        except Exception as exc:  # network hiccup -> brief bounded backoff
            last_error = exc
            network_failures += 1
            if network_failures >= 3:
                break
            time.sleep(3 * network_failures)
            seed += 1009
    raise RuntimeError(f"AI image generation failed after {attempt} attempts: {last_error}")


AI_IMAGE_SOURCE = "Pollinations AI (keyless free image API)"
AI_IMAGE_LICENSE = (
    "AI-generated via Pollinations free tier — review https://pollinations.ai/terms "
    "and confirm content rights before commercial use"
)
