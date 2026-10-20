"""
FFmpeg rendering pipeline (free / open source).

Fast path (default): every clip is fed into ONE FFmpeg process with a single filter graph
(Ken Burns zoompan per scene, xfade/acrossfade or concat, subtitles, music mix, watermark)
and ONE H.264/AAC encode. The previous pipeline re-encoded the growing video once per join
(O(n^2) encoder work) which could take 30-60 minutes on a free 512 MB host and appeared to
freeze on the later joins. Projects longer than config.MAX_SINGLE_GRAPH_CLIPS use the chunked
fallback (per-clip passes + pairwise joins), which shares the same watchdog protections.

Reliability:
  * every FFmpeg child runs in its own process group and is registered while alive;
  * an idle watchdog kills any child that emits no output for FFMPEG_IDLE_TIMEOUT seconds;
  * a hard wall-clock cap (RENDER_MAX_SECONDS) bounds the whole render;
  * cancel support kills the active group immediately;
  * progress is parsed from FFmpeg's -progress pipe on every pass, so the job row moves
    continuously instead of jumping between stages.
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

from . import media
from .config import (
    FFMPEG,
    FFMPEG_IDLE_TIMEOUT,
    FFMPEG_THREADS,
    MAX_SINGLE_GRAPH_CLIPS,
    PROJECTS_DIR,
    RENDER_MAX_SECONDS,
    X264_INTERIM_PRESET,
    X264_PRESET,
)

FPS = 30
TRANSITION_SECONDS = 0.7
VALID_TRANSITIONS = {"fade", "fadeblack", "slideleft", "slideright", "wiperight", "dissolve", "circleopen", "none"}


class RenderCancelled(RuntimeError):
    """Raised when the user (or the cancel endpoint) stops the render."""


# Every live FFmpeg child is registered here so a cancel request can kill it immediately.
_ACTIVE_PROCESSES: set[subprocess.Popen] = set()
_PROC_LOCK = threading.Lock()
_cancel_event: threading.Event | None = None


def request_cancel() -> None:
    """Signal cancellation and kill every active FFmpeg process group."""
    global _cancel_event
    if _cancel_event is not None:
        _cancel_event.set()
    with _PROC_LOCK:
        procs = list(_ACTIVE_PROCESSES)
    for proc in procs:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass


def media_duration(path: str | Path) -> float:
    """Probe duration without ffprobe by parsing FFmpeg's banner output."""
    proc = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)],
                          capture_output=True, text=True, timeout=60)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", proc.stderr)
    if not m:
        return 0.0
    h, mm, ss = m.groups()
    return int(h) * 3600 + int(mm) * 60 + float(ss)


def _run_ffmpeg(args: list[str], total_seconds: float | None = None,
                progress_cb: Callable[[float, str], None] | None = None, cwd: str | None = None,
                max_seconds: float | None = None) -> None:
    """Run FFmpeg with an idle watchdog, hard deadline and cancel support.

    progress_cb receives a 0..1 fraction of THIS call's total_seconds when known.
    """
    global _cancel_event
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-y", "-progress", "pipe:1", "-nostats"] + args
    # Bound glibc's per-thread malloc arenas: in tiny containers the default (8 x cores) can
    # make FFmpeg's RSS balloon well past its real working set and trigger an OOM kill.
    child_env = {**os.environ, "MALLOC_ARENA_MAX": os.environ.get("STORYFORGE_ARENA_MAX", "1")}
    # start_new_session=True gives the child its own process group so a cancel/idle-kill can
    # take out FFmpeg and every helper it may have spawned.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, cwd=cwd, bufsize=1, env=child_env,
                            start_new_session=True)
    assert proc.stdout is not None
    with _PROC_LOCK:
        _ACTIVE_PROCESSES.add(proc)
    tail: list[str] = []
    state = {"last_output": time.monotonic(), "killed": None}
    started = time.monotonic()

    def pump_err() -> None:
        for line in proc.stderr:  # type: ignore[union-attr]
            tail.append(line)
            if len(tail) > 60:
                tail.pop(0)

    def watchdog() -> None:
        # Fail loudly instead of hanging forever: no output for FFMPEG_IDLE_TIMEOUT seconds,
        # the overall render deadline, or an explicit cancel all terminate the child.
        while proc.poll() is None:
            time.sleep(2)
            idle = time.monotonic() - state["last_output"]
            if _cancel_event is not None and _cancel_event.is_set():
                state["killed"] = "cancel"
                _kill_group(proc)
                return
            if idle > FFMPEG_IDLE_TIMEOUT:
                state["killed"] = "idle"
                _kill_group(proc)
                return
            if max_seconds and time.monotonic() - started > max_seconds:
                state["killed"] = "deadline"
                _kill_group(proc)
                return

    def _kill_group(p: subprocess.Popen) -> None:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            time.sleep(5)
            if p.poll() is None:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    t_err = threading.Thread(target=pump_err, daemon=True)
    t_dog = threading.Thread(target=watchdog, daemon=True)
    t_err.start()
    t_dog.start()
    try:
        for line in proc.stdout:
            state["last_output"] = time.monotonic()
            line = line.strip()
            # FFmpeg prints both out_time_ms and out_time_us; despite the name, both are microseconds.
            if progress_cb and total_seconds and (
                line.startswith("out_time_ms=") or line.startswith("out_time_us=")
            ):
                try:
                    secs = int(line.split("=", 1)[1]) / 1_000_000
                    pct = max(0.0, min(0.99, secs / total_seconds))
                    progress_cb(pct, f"rendering {secs:.1f}s / {total_seconds:.1f}s")
                except ValueError:
                    pass
        proc.wait()
    finally:
        with _PROC_LOCK:
            _ACTIVE_PROCESSES.discard(proc)
    t_err.join(timeout=5)
    if state["killed"] == "cancel" or (_cancel_event is not None and _cancel_event.is_set()):
        raise RenderCancelled("Render cancelled.")
    if proc.returncode != 0:
        if state["killed"] == "idle":
            raise RuntimeError(
                f"FFmpeg made no progress for {FFMPEG_IDLE_TIMEOUT}s and was stopped. "
                "Try the fast 480p preview or split the video into fewer scenes.\n" + "".join(tail)[-700:]
            )
        if state["killed"] == "deadline":
            raise RuntimeError(
                f"Render exceeded the {RENDER_MAX_SECONDS}s safety limit and was stopped. "
                "Use fast 480p preview or fewer/shorter scenes."
            )
        raise RuntimeError("FFmpeg error:\n" + "".join(tail)[-900:])


def _zoom_expr(motion: str, frames: int) -> tuple[str, str, str]:
    n = max(frames, 1)
    center_x = "iw/2-(iw/zoom/2)"
    center_y = "ih/2-(ih/zoom/2)"
    if motion == "zoom_in":
        return (f"min(1.0+0.0009*on,1.35)", center_x, center_y)
    if motion == "zoom_out":
        return ("if(lte(on,0),1.35,max(1.0,1.35-0.0009*on))", center_x, center_y)
    if motion == "pan_left":
        return ("1.15", f"(iw-iw/zoom)*on/{n}", "(ih-ih/zoom)/2")
    if motion == "pan_right":
        return ("1.15", f"(iw-iw/zoom)*(1-on/{n})", "(ih-ih/zoom)/2")
    return ("1.0", "0", "0")


def _srt_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def _caption_chunks(text: str, max_words: int = 12) -> list[str]:
    """Split narration into readable cues: sentences first, then word-limited wraps."""
    sentences = re.split(r"(?<=[.!?])\s+", text.replace("\n", " ").strip())
    chunks: list[str] = []
    for sentence in sentences:
        words = sentence.split()
        if not words:
            continue
        while len(words) > max_words:
            chunks.append(" ".join(words[:max_words]))
            words = words[max_words:]
        if words:
            chunks.append(" ".join(words))
    return chunks


def _write_srt(entries: list[dict[str, Any]], path: Path) -> None:
    out: list[str] = []
    idx = 1
    for e in entries:
        text = (e.get("caption") or e.get("narration") or "").strip()
        if not text:
            continue
        chunks = _caption_chunks(text)
        window = max(0.1, float(e["end"]) - float(e["start"]))
        weights = [max(1, len(c.split())) for c in chunks]
        total_w = sum(weights)
        cursor = float(e["start"])
        for chunk, weight in zip(chunks, weights):
            dur = window * weight / total_w
            end = min(float(e["end"]), cursor + dur)
            out.append(f"{idx}\n{_srt_time(cursor)} --> {_srt_time(end)}\n{chunk}\n")
            cursor = end
            idx += 1
    path.write_text("\n".join(out), encoding="utf-8")


def _plan_clips(project: dict[str, Any], aspect: str, resolution: str,
                skip_title: bool = False) -> list[dict[str, Any]]:
    """Resolve every scene's image/audio/duration and prepend/append title cards."""
    pid = project["id"]
    tl = project.get("timeline", {})
    scenes = project.get("scenes", [])
    assets_by_id = {a["id"]: a for a in project.get("assets", [])}

    planned: list[dict[str, Any]] = []
    for sc in scenes:
        img = None
        if sc.get("image_asset_id") and sc["image_asset_id"] in assets_by_id:
            cand = Path(assets_by_id[sc["image_asset_id"]]["path"])
            if cand.exists():
                img = str(cand)
        if img is None:
            img = media.create_placeholder(pid, sc["id"], sc.get("visual_prompt", sc.get("heading", "")),
                                           project.get("style", {}), aspect, resolution)
        audio = None
        if sc.get("audio_asset_id") and sc["audio_asset_id"] in assets_by_id:
            cand = Path(assets_by_id[sc["audio_asset_id"]]["path"])
            if cand.exists():
                audio = str(cand)
        dur = float(sc.get("duration") or 5.0)
        if audio:
            dur = max(dur, media_duration(audio) + 0.5)
        planned.append({**sc, "_img": img, "_audio": audio, "_dur": round(dur, 2),
                        "_transition": sc.get("transition", tl.get("transition", "fade")),
                        "_motion": sc.get("motion", "zoom_in")})

    clips: list[dict[str, Any]] = []
    if tl.get("title_card", True) and not skip_title:
        card = media.create_title_card(pid, project.get("script", {}).get("title", project["name"]),
                                       project.get("script", {}).get("logline", "")[:120],
                                       aspect, resolution, "intro")
        clips.append({"path": "", "dur": 3.5, "kind": "intro", "transition": "fade",
                      "img": card, "audio": None, "motion": "zoom_in", "caption": ""})
    for p in planned:
        clips.append({"path": "", "dur": p["_dur"], "kind": "scene", "scene": p,
                      "transition": p["_transition"], "img": p["_img"], "audio": p["_audio"],
                      "motion": p["_motion"], "caption": p.get("caption_text") or p.get("narration", ""),
                      "heading": p.get("heading", "")})
    if tl.get("outro", False):
        card = media.create_title_card(pid, "The End", project.get("name", ""), aspect, resolution, "outro")
        clips.append({"path": "", "dur": 4.0, "kind": "outro", "transition": "fade",
                      "img": card, "audio": None, "motion": "zoom_out", "caption": ""})
    return clips


def _timings_and_total(clips: list[dict[str, Any]], tdur: float) -> tuple[list[dict[str, Any]], float]:
    timings: list[dict[str, Any]] = []
    cursor = 0.0
    for i, c in enumerate(clips):
        start = cursor - (i * tdur if i else 0.0)
        c["_start"] = max(0.0, start)
        if c["kind"] == "scene":
            timings.append({
                "scene_id": c["scene"]["id"], "heading": c.get("heading", ""),
                "start": c["_start"], "end": c["_start"] + c["dur"] - tdur,
                "caption": c["caption"], "narration": c["caption"],
            })
        cursor += c["dur"]
    total = cursor - tdur * (len(clips) - 1)
    return timings, total


def _encode_settings(resolution: str) -> tuple[str, int]:
    if resolution in media.PREVIEW_RESOLUTIONS:
        # Fast preview: speed-first preset, slightly higher CRF (draft quality).
        return X264_INTERIM_PRESET, 26
    if resolution == "1080p":
        return X264_PRESET, 20
    return X264_PRESET, 23


def _clip_video_filter(width: int, height: int, clip: dict[str, Any], fps: int,
                       is_preview: bool) -> str:
    """Per-clip video chain. Draft previews use static framed images (no per-frame zoompan
    work, which is expensive on throttled free CPUs); full renders keep the Ken Burns motion."""
    base = (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1")
    if is_preview:
        return f"{base},fps={fps},format=yuv420p"
    frames = int(clip["dur"] * fps)
    z, x, y = _zoom_expr(clip["motion"], frames)
    return (f"{base},zoompan=z='{z}':x='{x}':y='{y}':d=1:s={width}x{height}:fps={fps},"
            f"fps={fps},format=yuv420p")


def render_project(project: dict[str, Any], progress_cb: Callable[[float, str], None],
                   resolution_override: str | None = None) -> dict[str, Any]:
    global _cancel_event
    _cancel_event = threading.Event()
    deadline = time.monotonic() + RENDER_MAX_SECONDS
    pid = project["id"]
    tl = project.get("timeline", {})
    aspect = tl.get("aspect", "16:9")
    # A "480p" fast-preview override can be passed per render without changing the project.
    resolution = resolution_override or tl.get("resolution", "720p")
    width, height = media.dimensions(aspect, resolution)
    scenes = project.get("scenes", [])
    if not scenes:
        raise RuntimeError("This project has no scenes. Build the storyboard before exporting.")

    root = PROJECTS_DIR / pid
    temp = root / "temp" / f"render_{int(time.time())}"
    temp.mkdir(parents=True, exist_ok=True)
    assets_by_id = {a["id"]: a for a in project.get("assets", [])}

    # Draft previews: 360p/480p, 20 fps, static framed images and no title card - the cheapest
    # possible encode of the real storyboard so the free host finishes it inside ten minutes.
    is_preview = resolution in media.PREVIEW_RESOLUTIONS
    progress_cb(0.02, "preparing frames")
    clips = _plan_clips(project, aspect, resolution, skip_title=is_preview)
    use_transitions = any(c["transition"] not in ("none", "") for c in clips[1:])
    tdur = min(TRANSITION_SECONDS, min(c["dur"] for c in clips) / 2) if use_transitions else 0.0
    timings, total = _timings_and_total(clips, tdur)

    srt_path = temp / "subs.srt"
    if tl.get("burn_captions", True):
        _write_srt(timings, srt_path)

    music_path = None
    if tl.get("music_asset_id") and tl["music_asset_id"] in assets_by_id:
        music_path = assets_by_id[tl["music_asset_id"]]["path"]
    wm_path = None
    if tl.get("watermark_asset_id") and tl["watermark_asset_id"] in assets_by_id:
        wm_path = assets_by_id[tl["watermark_asset_id"]]["path"]

    out_dir = root / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{project['name'].replace(' ', '_')[:40]}_{int(time.time())}.mp4"
    # Encode into a .part file and atomically rename on success: a killed/cancelled render can
    # never leave a truncated MP4 that looks like a finished export.
    part_file = out_file.with_suffix(".part.mp4")
    fps = media.PREVIEW_FPS if is_preview else FPS
    preset, crf = _encode_settings(resolution)

    try:
        if len(clips) <= MAX_SINGLE_GRAPH_CLIPS:
            # Fast path: per-clip files, bounded joins, one quality encode.
            _render_single_graph(
                clips, width, height, total, tdur, use_transitions, srt_path,
                music_path, wm_path, tl, part_file, temp, preset, crf, fps, resolution,
                is_preview, progress_cb, deadline,
            )
        else:
            _render_chunked(
                clips, width, height, total, tdur, use_transitions, srt_path,
                music_path, wm_path, tl, part_file, temp, preset, crf, fps, is_preview,
                progress_cb, deadline,
            )
    except RenderCancelled:
        part_file.unlink(missing_ok=True)
        shutil.rmtree(temp, ignore_errors=True)
        raise
    except Exception:
        part_file.unlink(missing_ok=True)
        shutil.rmtree(temp, ignore_errors=True)
        raise
    part_file.replace(out_file)
    progress_cb(1.0, "finalizing MP4")
    result = {
        "file": str(out_file),
        "duration": round(media_duration(out_file), 2),
        "width": width,
        "height": height,
        "aspect": aspect,
        "resolution": resolution,
        "scene_timings": timings,
        "used_placeholders": [c["heading"] for c in clips if c["kind"] == "scene"
                              and "placeholder" in (c.get("img") or "")],
        "used_transitions": use_transitions,
        "music": bool(music_path),
        "captions_burned": tl.get("burn_captions", True),
    }
    # Intermediates are no longer needed; free the (small) container disk immediately.
    shutil.rmtree(temp, ignore_errors=True)
    return result


# Max clip-file inputs per join process, chosen so FFmpeg's measured peak PSS stays well
# under the 512 MB container (480p ~275 MB at 5 inputs, 720p ~280 MB at 3, 1080p ~190 MB at 2).
JOIN_GROUP_SIZES = {"360p": 6, "480p": 5, "720p": 3, "1080p": 2}


def _caption_style() -> str:
    return ("FontName=DejaVu Sans,FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=36")


def _append_final_filters(fc: list[str], inputs: list[str], vl: str, al: str, next_idx: int,
                          total: float, srt_path: Path, music_path: str | None,
                          wm_path: str | None, tl: dict[str, Any], width: int) -> tuple[str, str, int]:
    """Music mix, burned captions and watermark appended to an existing filter graph."""
    if music_path:
        inputs += ["-stream_loop", "-1", "-i", music_path]
        fc.append(f"[{next_idx}:a]aformat=sample_rates=44100:channel_layouts=stereo,"
                  f"atrim=0:{total:.2f},asetpts=PTS-STARTPTS,volume=0.22[bg]")
        fc.append(f"[{al}][bg]amix=inputs=2:duration=first:dropout_transition=0,"
                  "alimiter=limit=0.95[aout]")
        al = "aout"
        next_idx += 1
    if tl.get("burn_captions", True) and srt_path.exists():
        fc.append(f"[{vl}]subtitles=subs.srt:force_style='{_caption_style()}'[vsub]")
        vl = "vsub"
    if wm_path:
        pos = tl.get("watermark_position", "bottom-right")
        positions = {
            "top-left": "24:24", "top-right": "W-w-24:24",
            "bottom-left": "24:H-h-24", "bottom-right": "W-w-24:H-h-24",
        }
        inputs += ["-i", wm_path]
        fc.append(f"[{next_idx}:v]scale={max(90, width // 6)}:-1[wms]")
        fc.append(f"[{vl}][wms]overlay={positions.get(pos, positions['bottom-right'])}[vout]")
        vl = "vout"
    return vl, al, next_idx


def _final_passthrough_filters(joined: str, total: float, fps: int,
                               srt_path: Path, music_path: str | None, wm_path: str | None,
                               tl: dict[str, Any], width: int, temp: Path,
                               preset: str, crf: int, out_file: Path,
                               progress_cb: Callable[[float, str], None],
                               deadline: float) -> None:
    """Subtitles / music / watermark + the quality encode on a single input (small graph)."""
    fc: list[str] = []
    args: list[str] = ["-i", joined]
    vl, al, _ = _append_final_filters(fc, args, "0:v", "0:a", 1, total,
                                      srt_path, music_path, wm_path, tl, width)
    if not fc:
        shutil.copyfile(joined, out_file)
        return
    audio_map = al if al == "0:a" else f"[{al}]"
    args += ["-filter_complex", ";".join(fc),
             "-map", f"[{vl}]", "-map", audio_map,
             "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
             "-pix_fmt", "yuv420p", "-r", str(fps),
             "-threads", str(FFMPEG_THREADS), "-filter_threads", "1",
             "-filter_complex_threads", "1",
             "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out_file)]

    def cb(p: float, msg: str) -> None:
        progress_cb(0.78 + 0.19 * p, msg)

    _run_ffmpeg(args, total_seconds=total, progress_cb=cb, cwd=str(temp),
                max_seconds=max(30.0, deadline - time.monotonic()))


def _render_single_graph(clips: list[dict[str, Any]], width: int, height: int, total: float,
                         tdur: float, use_transitions: bool, srt_path: Path,
                         music_path: str | None, wm_path: str | None, tl: dict[str, Any],
                         out_file: Path, temp: Path, preset: str, crf: int, fps: int,
                         resolution: str, is_preview: bool,
                         progress_cb: Callable[[float, str], None], deadline: float) -> None:
    """Memory-bounded fast path (safe on a 512 MB container).

    Stage 1: one small FFmpeg process per clip normalizes image+audio into a CFR MP4 with the
    Ken Burns motion (a single input each, tiny RSS).
    Stage 2: hierarchical joins in small input groups; the LAST join process also burns
    captions and applies music/watermark with the quality encoder, so the full video is
    encoded only once after the per-clip work.
    """
    n = len(clips)

    def remaining() -> float:
        return max(30.0, deadline - time.monotonic())

    # ---------- Stage 1: per-clip normalized files ----------
    for i, clip in enumerate(clips):
        out_clip = temp / f"clip_{i:03d}.mp4"
        vf = _clip_video_filter(width, height, clip, fps, is_preview)
        args = ["-framerate", str(fps), "-loop", "1", "-t", str(clip["dur"]), "-i", clip["img"]]
        if clip["audio"]:
            args += ["-i", clip["audio"]]
        else:
            args += ["-f", "lavfi", "-t", str(clip["dur"]), "-i", "anullsrc=r=44100:cl=stereo"]
        args += [
            "-filter_complex",
            f"[0:v]{vf}[v];[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"apad,atrim=0:{clip['dur']},asetpts=PTS-STARTPTS[a]",
            "-map", "[v]", "-map", "[a]", "-t", str(clip["dur"]),
            "-c:v", "libx264", "-preset", X264_INTERIM_PRESET, "-crf", "26",
            "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "160k",
            "-threads", str(FFMPEG_THREADS), "-filter_threads", "1",
            "-filter_complex_threads", "1", str(out_clip),
        ]

        def cb_a(p: float, msg: str, idx=i) -> None:
            progress_cb(0.03 + 0.42 * (idx + p) / n, msg)

        _run_ffmpeg(args, total_seconds=clip["dur"], progress_cb=cb_a, max_seconds=remaining())
        clip["path"] = str(out_clip)

    transitions = [c.get("transition", "fade") for c in clips[1:]]

    if not use_transitions:
        # Uniform clip files: concat demuxer stream-copies with almost no memory or CPU.
        list_file = temp / "concat.txt"
        list_file.write_text(
            "".join(f"file '{Path(c['path']).name}'\n" for c in clips), encoding="utf-8")
        joined = str(temp / "joined.mp4")
        _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", "concat.txt",
                     "-c", "copy", joined], cwd=str(temp), max_seconds=remaining())
        progress_cb(0.50, "clips joined")
        _final_passthrough_filters(
            joined, total, fps, srt_path, music_path, wm_path, tl, width, temp,
            preset, crf, out_file, progress_cb, deadline,
        )
        return

    # ---------- Stage 2: hierarchical joins, finals folded into the last process ----------
    group_size = JOIN_GROUP_SIZES.get(resolution, 3)
    nodes = [{"path": c["path"], "dur": float(c["dur"]), "start": i, "count": 1}
             for i, c in enumerate(clips)]
    total_joins = max(1, len(nodes) - 1)
    done_joins = 0
    round_no = 0
    while len(nodes) > 1:
        groups = [nodes[i:i + group_size] for i in range(0, len(nodes), group_size)]
        final_round = len(groups) == 1
        merged: list[dict[str, Any]] = []
        for gi, group in enumerate(groups):
            if len(group) == 1:
                merged.append(group[0])
                continue
            args: list[str] = []
            for node in group:
                args += ["-i", node["path"]]
            fc: list[str] = []
            for idx in range(len(group)):
                fc.append(f"[{idx}:a]aformat=sample_rates=44100:channel_layouts=stereo,"
                          f"asetpts=PTS-STARTPTS[a{idx}]")
            vl, al = "0:v", "a0"
            cur_dur = float(group[0]["dur"])
            for k in range(1, len(group)):
                boundary = group[k - 1]["start"] + group[k - 1]["count"] - 1
                tr = transitions[boundary] if boundary < len(transitions) else "fade"
                if tr not in VALID_TRANSITIONS:
                    tr = "fade"
                offset = max(0.0, cur_dur - tdur - 1.0 / fps)
                outv, outa = f"gv{gi}_{k}", f"ga{gi}_{k}"
                fc.append(
                    f"[{vl}][{k}:v]xfade=transition={tr}:duration={tdur:.3f}:offset={offset:.3f}[{outv}];"
                    f"[{al}][a{k}]acrossfade=d={tdur:.3f}[{outa}]"
                )
                vl, al = outv, outa
                cur_dur += float(group[k]["dur"]) - tdur
            joins_in_group = len(group) - 1
            if final_round:
                # Last process: music, captions and watermark join the same graph, then the
                # single quality encode writes the finished MP4 directly.
                vl, al, _ = _append_final_filters(
                    fc, args, vl, al, len(group), total, srt_path, music_path, wm_path, tl, width)
                target = out_file
                out_preset, out_crf = preset, crf
                faststart = ["-movflags", "+faststart"]
                cwd = str(temp)
            else:
                target = temp / f"join_r{round_no}_{gi:03d}.mp4"
                out_preset, out_crf, faststart, cwd = X264_INTERIM_PRESET, "26", [], None
            audio_map = al if al in ("0:a", "aout") else f"[{al}]"
            args += [
                "-filter_complex", ";".join(fc),
                "-map", f"[{vl}]", "-map", audio_map,
                "-c:v", "libx264", "-preset", out_preset, "-crf", str(out_crf),
                "-pix_fmt", "yuv420p", "-r", str(fps),
                "-threads", str(FFMPEG_THREADS), "-filter_threads", "1",
                "-filter_complex_threads", "1",
                "-c:a", "aac", "-b:a", "160k", *faststart, str(target),
            ]
            join_total = sum(float(nd["dur"]) for nd in group)
            base_done = done_joins

            if final_round:
                def join_cb(p: float, msg: str) -> None:
                    progress_cb(0.78 + 0.19 * p, msg)
            else:
                def join_cb(p: float, _msg: str, b=base_done, k=joins_in_group) -> None:
                    frac = (b + k * p) / total_joins
                    progress_cb(0.45 + 0.30 * frac,
                                f"joining clips {min(total_joins, b + k)}/{total_joins}")

            _run_ffmpeg(args, total_seconds=join_total, progress_cb=join_cb,
                        cwd=cwd, max_seconds=remaining())
            merged.append({"path": str(target), "dur": cur_dur,
                           "start": group[0]["start"],
                           "count": sum(nd["count"] for nd in group)})
            done_joins += joins_in_group
            if not final_round:
                progress_cb(0.45 + 0.30 * done_joins / total_joins,
                            f"joining clips {done_joins}/{total_joins}")
        nodes = merged
        round_no += 1


def _render_chunked(clips: list[dict[str, Any]], width: int, height: int, total: float,
                    tdur: float, use_transitions: bool, srt_path: Path,
                    music_path: str | None, wm_path: str | None, tl: dict[str, Any],
                    out_file: Path, temp: Path, preset: str, crf: int, fps: int, is_preview: bool,
                    progress_cb: Callable[[float, str], None], deadline: float) -> None:
    """Fallback for very long projects: per-clip encodes + pairwise joins (bounded memory)."""
    def remaining() -> float:
        return max(30.0, deadline - time.monotonic())

    # Pass A: normalized per-clip renders.
    for i, clip in enumerate(clips):
        out_clip = temp / f"clip_{i:03d}.mp4"
        vf = _clip_video_filter(width, height, clip, fps, is_preview)
        args = ["-framerate", str(fps), "-loop", "1", "-t", str(clip["dur"]), "-i", clip["img"]]
        if clip["audio"]:
            args += ["-i", clip["audio"]]
        else:
            args += ["-f", "lavfi", "-t", str(clip["dur"]), "-i", "anullsrc=r=44100:cl=stereo"]
        args += [
            "-filter_complex",
            f"[0:v]{vf}[v];[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
            f"apad,atrim=0:{clip['dur']},asetpts=PTS-STARTPTS[a]",
            "-map", "[v]", "-map", "[a]", "-t", str(clip["dur"]),
            "-c:v", "libx264", "-preset", X264_INTERIM_PRESET, "-crf", "26",
            "-c:a", "aac", "-b:a", "160k",
            "-threads", str(FFMPEG_THREADS), "-filter_threads", "1",
            "-filter_complex_threads", "1", str(out_clip),
        ]
        def cb_a(p: float, msg: str, idx=i) -> None:
            progress_cb(0.03 + 0.40 * (idx + p) / len(clips), msg)

        _run_ffmpeg(args, total_seconds=clip["dur"], progress_cb=cb_a, max_seconds=remaining())
        clip["path"] = str(out_clip)

    n_clips = len(clips)
    joined = clips[0]["path"]
    if use_transitions:
        dur_cur = float(clips[0]["dur"])
        for i in range(1, n_clips):
            tr = clips[i]["transition"] if clips[i]["transition"] in VALID_TRANSITIONS else "fade"
            probe = media_duration(joined)
            if probe > 0:
                dur_cur = probe
            offset = max(0.0, dur_cur - tdur - 1.0 / fps)
            out_join = temp / f"join_{i:03d}.mp4"
            join_args = [
                "-i", joined, "-i", clips[i]["path"],
                "-filter_complex",
                f"[0:v][1:v]xfade=transition={tr}:duration={tdur:.2f}:offset={offset:.3f}[v];"
                f"[0:a][1:a]acrossfade=d={tdur:.2f}[a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", X264_INTERIM_PRESET, "-crf", "26",
                "-pix_fmt", "yuv420p", "-r", str(fps),
                "-c:a", "aac", "-b:a", "160k",
                "-threads", str(FFMPEG_THREADS), "-filter_threads", "1",
                "-filter_complex_threads", "1", str(out_join),
            ]
            def cb_j(p: float, msg: str, idx=i) -> None:
                progress_cb(0.45 + 0.25 * (idx - 1 + p) / max(1, n_clips - 1), msg)

            _run_ffmpeg(join_args, total_seconds=dur_cur + clips[i]["dur"],
                        progress_cb=cb_j, max_seconds=remaining())
            joined = str(out_join)
            dur_cur = dur_cur + float(clips[i]["dur"]) - tdur
    else:
        list_file = temp / "concat.txt"
        list_file.write_text(
            "".join(f"file '{Path(c['path']).name}'\n" for c in clips), encoding="utf-8")
        joined_concat = temp / "joined.mp4"
        _run_ffmpeg(["-f", "concat", "-safe", "0", "-i", "concat.txt",
                     "-c", "copy", str(joined_concat)], cwd=str(temp), max_seconds=remaining())
        joined = str(joined_concat)

    _final_passthrough_filters(
        joined, total, fps, srt_path, music_path, wm_path, tl, width, temp,
        preset, crf, out_file, progress_cb, deadline,
    )
