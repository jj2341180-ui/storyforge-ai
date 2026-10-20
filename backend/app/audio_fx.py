"""Procedural sound effects and background music for AI Shorts.

Everything here is SYNTHESIZED with FFmpeg's built-in audio sources (noise, sine
oscillators) and filters. No third-party audio files are downloaded, so every track is
royalty-free by construction and works fully offline on the free host.

Design notes for the 512 MB free container:
  * short-lived FFmpeg processes only (the same watchdog-friendly pattern as renderer.py);
  * mono 44.1 kHz MP3 intermediates, one encode per stem, one final mix encode.
"""
from __future__ import annotations

import math
import random
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .config import DATA_DIR, FFMPEG, FFMPEG_THREADS

FX_DIR = DATA_DIR / "shorts" / "audio_fx"
FX_DIR.mkdir(parents=True, exist_ok=True)

SR = 44100

# ---------------------------------------------------------------- keyword → ambience

# Ordered (keyword group, preset). First matching group wins; "forest" intentionally comes
# before generic "wind" so bird layers are included.
_KEYWORD_PRESETS: list[tuple[tuple[str, ...], str]] = [
    (("ocean", "sea", "beach", "wave", "ship", "harbor", "coast"), "ocean"),
    (("rain", "storm", "thunder", "umbrella"), "rain"),
    (("forest", "jungle", "woods", "trees", "leaves", "bird", "garden", "wildlife"), "forest"),
    (("city", "street", "traffic", "crowd", "market", "urban", "car", "train"), "city"),
    (("fire", "flame", "campfire", "ember", "lava", "burn"), "fire"),
    (("dragon", "monster", "growl", "beast", "roar"), "dragon"),
    (("magic", "sparkle", "wizard", "spell", "fairy", "glow", "enchanted", "mystic"), "magic"),
    (("fight", "battle", "chase", "run", "running", "jump", "explosion", "impact", "heroic"), "action"),
    (("night", "moon", "calm", "silent", "myster", "shadow", "dream", "sleep"), "night"),
    (("wind", "mountain", "cliff", "snow", "cloud", "sky"), "wind"),
    (("river", "water", "stream", "waterfall", "lake"), "ocean"),
]

MOOD_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("fight", "battle", "chase", "hero", "epic", "action", "dragon"), "dramatic"),
    (("myster", "secret", "shadow", "dark", "night", "magic", "enchanted"), "suspenseful"),
    (("love", "loss", "tear", "cry", "memory", "goodbye", "emotion"), "emotional"),
    (("calm", "peace", "gentle", "dream", "sleep", "garden", "soft"), "peaceful"),
]


def detect_preset(text: str) -> str:
    t = (text or "").lower()
    for keys, preset in _KEYWORD_PRESETS:
        if any(k in t for k in keys):
            return preset
    return "wind"


def detect_mood(text: str, fallback: str = "adventurous") -> str:
    t = (text or "").lower()
    for keys, mood in MOOD_KEYWORDS:
        if any(k in t for k in keys):
            return mood
    return fallback


# ---------------------------------------------------------------- ffmpeg helpers

def _run(cmd: list[str], timeout: int = 180) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"audio synthesis failed: {proc.stderr[-400:]}")


def _mp3_out(prefix: str) -> Path:
    return FX_DIR / f"{prefix}_{uuid.uuid4().hex[:8]}.mp3"


def _lavfi(graph: str, out: Path, duration: float, timeout: int = 180) -> Path:
    """Render one lavfi source graph to a mono MP3 trimmed exactly to duration."""
    _run([
        FFMPEG, "-hide_banner", "-nostdin", "-y",
        "-f", "lavfi", "-i", graph,
        "-t", f"{duration:.3f}",
        "-threads", str(FFMPEG_THREADS),
        "-ac", "1", "-ar", str(SR), "-c:a", "libmp3lame", "-q:a", "5",
        str(out),
    ], timeout=timeout)
    return out


def _mix(inputs: list[tuple[Path, float]], out: Path, duration: float,
         weights: list[float] | None = None) -> Path:
    """Mix several MP3s (each padded/trimmed to duration) into one mono MP3."""
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-y"]
    for p, _ in inputs:
        cmd += ["-i", str(p)]
    n = len(inputs)
    w = weights or [1.0] * n
    labels = "".join(f"[{i}:a]" for i in range(n))
    wspec = "weights=" + " ".join(f"{x:.3f}" for x in w)
    graph = (f"{labels}amix=inputs={n}:duration=longest:normalize=0:{wspec},"
             f"apad=whole_dur={duration:.3f},atrim=0:{duration:.3f},alimiter=limit=0.95")
    cmd += ["-filter_complex", graph, "-threads", str(FFMPEG_THREADS),
            "-ac", "1", "-ar", str(SR), "-c:a", "libmp3lame", "-q:a", "5", str(out)]
    _run(cmd)
    return out


# ---------------------------------------------------------------- sound-effect presets

def _delayed_mix(parts: list[tuple[Path, float]], duration: float, out: Path,
                 volume: float = 0.9) -> Path:
    """Lay short clips onto a finite silence bed at per-clip offsets (seconds)."""
    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-y",
           "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono:duration={duration:.3f}"]
    for p, _ in parts:
        cmd += ["-i", str(p)]
    chains = [f"[{i+1}:a]adelay={int(max(0.0, dl)*1000)}|{int(max(0.0, dl)*1000)}[d{i}]"
              for i, (_, dl) in enumerate(parts)]
    joined = "".join(f"[d{i}]" for i in range(len(parts)))
    graph = ";".join(chains) + (
        f";[0:a]{joined}amix=inputs={len(parts)+1}:duration=first:normalize=0,"
        f"atrim=0:{duration:.3f},volume={volume}")
    cmd += ["-filter_complex", graph, "-threads", str(FFMPEG_THREADS),
            "-ac", "1", "-ar", str(SR), "-c:a", "libmp3lame", "-q:a", "5",
            "-t", f"{duration:.3f}", str(out)]
    _run(cmd, timeout=60)
    return out


def _chirp_bed(duration: float, rng: random.Random) -> Path:
    """Light bird-song: short bright tones placed at random offsets."""
    parts: list[tuple[Path, float]] = []
    count = max(2, int(duration / 3.0))
    cursor = 0.2
    for _ in range(count):
        f0 = rng.choice((1800, 2200, 2600, 3100))
        d = rng.uniform(0.12, 0.25)
        p = _mp3_out("chirp")
        graph = (f"sine=frequency={f0}:duration={d:.3f},"
                 f"afade=t=in:st=0:d=0.02,afade=t=out:st={max(0,d-0.05):.3f}:d=0.05,volume=0.25")
        _lavfi(graph, p, d, timeout=60)
        parts.append((p, cursor))
        cursor += rng.uniform(0.8, 2.2)
    return _delayed_mix(parts, duration, _mp3_out("birds"), volume=0.9)


def sfx_for_scene(text: str, duration: float, seed: int | None = None) -> tuple[Path, str]:
    """Return (mp3 path, preset name) for an ambient bed matching the scene text."""
    rng = random.Random(seed if seed is not None else random.randint(0, 9_999_999))
    preset = detect_preset(text)
    d = max(1.0, float(duration))
    out = _mp3_out(f"sfx_{preset}")

    if preset == "ocean":
        graph = ("anoisesrc=color=brown:duration=D,lowpass=f=800,"
                 "tremolo=f=0.11:d=0.7,volume=0.55").replace("D", f"{d:.3f}")
    elif preset == "rain":
        graph = ("anoisesrc=color=white:duration=D,highpass=f=1200,lowpass=f=6500,"
                 "volume=0.4").replace("D", f"{d:.3f}")
    elif preset == "forest":
        wind = _mp3_out("wind")
        _lavfi(("anoisesrc=color=pink:duration=D,lowpass=f=700,"
                "tremolo=f=0.18:d=0.4,volume=0.4").replace("D", f"{d:.3f}"), wind, d)
        birds = _chirp_bed(d, rng)
        return _mix([(wind, d), (birds, d)], out, d, weights=[0.8, 0.5]), preset
    elif preset == "city":
        graph = ("anoisesrc=color=white:duration=D,bandpass=f=900:width_type=h:w=1400,"
                 "tremolo=f=0.6:d=0.25,volume=0.32").replace("D", f"{d:.3f}")
    elif preset == "fire":
        graph = ("anoisesrc=color=pink:duration=D,bandpass=f=500:width_type=h:w=900,"
                 "tremolo=f=7:d=0.8,volume=0.5").replace("D", f"{d:.3f}")
    elif preset == "dragon":
        drone = _mp3_out("drone")
        _lavfi(f"sine=frequency=62:duration={d:.3f},tremolo=f=4.5:d=0.6,volume=0.5", drone, d)
        rumble = _mp3_out("rumble")
        _lavfi(("anoisesrc=color=brown:duration=D,lowpass=f=300,volume=0.45"
                ).replace("D", f"{d:.3f}"), rumble, d)
        return _mix([(drone, d), (rumble, d)], out, d, weights=[0.9, 0.7]), preset
    elif preset == "magic":
        # Pentatonic sparkle arpeggio (A minor pentatonic), gentle and bright.
        scale = (440.0, 523.25, 587.33, 659.25, 783.99, 880.0)
        note_d = min(0.6, d / 6.0)
        parts = []
        t = 0.1
        while t < d - 0.2:
            f = rng.choice(scale)
            p = _mp3_out("spark")
            _lavfi((f"sine=frequency={f:.1f}:duration={note_d:.3f},"
                    f"afade=t=in:st=0:d=0.05,afade=t=out:st={note_d-0.12:.3f}:d=0.12,volume=0.22"),
                   p, note_d)
            parts.append((p, t))
            t += rng.uniform(note_d * 0.8, note_d * 1.6)
        _delayed_mix(parts, d, out, volume=0.9)
        return out, preset
    elif preset == "action":
        # Driving low pulse (impacts/footsteps) under a tense noise bed.
        pulse_gap = 0.55
        parts = []
        t = 0.05
        while t < d - 0.2:
            p = _mp3_out("thump")
            _lavfi("sine=frequency=70:duration=0.22,afade=t=in:st=0:d=0.01,"
                   "afade=t=out:st=0.08:d=0.14,volume=0.55", p, 0.22)
            parts.append((p, t))
            t += pulse_gap
        bed = _mp3_out("actionbed")
        _lavfi(("anoisesrc=color=white:duration=D,bandpass=f=700:width_type=h:w=1200,"
                "volume=0.18").replace("D", f"{d:.3f}"), bed, d)
        thumps = _delayed_mix(parts, d, _mp3_out("thumps"), volume=0.95)
        _mix([(bed, d), (thumps, d)], out, d, weights=[0.6, 0.9])
        return out, preset
    else:  # wind / night: soft filtered noise, night adds a low calm drone
        graph = ("anoisesrc=color=pink:duration=D,lowpass=f=600,"
                 "tremolo=f=0.14:d=0.45,volume=0.4").replace("D", f"{d:.3f}")
    _lavfi(graph, out, d)
    if preset == "night":
        drone = _mp3_out("nightdrone")
        _lavfi("sine=frequency=110:duration=D,volume=0.12".replace("D", f"{d:.3f}"), drone, d)
        mixed = _mp3_out("nightmix")
        _mix([(out, d), (drone, d)], mixed, d, weights=[0.8, 0.6])
        return mixed, preset
    return out, preset


# ---------------------------------------------------------------- background music

# Note name -> frequency (Hz), octave 2/3 range for soft pads.
_NOTES = {
    "C2": 65.41, "D2": 73.42, "E2": 82.41, "F2": 87.31, "G2": 98.00, "A2": 110.0, "Bb2": 116.54,
    "C3": 130.81, "D3": 146.83, "E3": 164.81, "F3": 174.61, "G3": 196.0, "A3": 220.0, "Bb3": 233.08, "B3": 246.94,
}

_PROGRESSIONS: dict[str, list[tuple[str, str, str]]] = {
    # each chord = (root, third, fifth) pad triad
    "adventurous": [("A2", "C3", "E3"), ("F2", "A2", "C3"), ("C3", "E3", "G3"), ("G2", "B3", "D3")],
    "suspenseful": [("A2", "C3", "E3"), ("E2", "G3", "B3"), ("D3", "F3", "A3"), ("E2", "G3", "B3")],
    "peaceful": [("C3", "E3", "G3"), ("G2", "B3", "D3"), ("A2", "C3", "E3"), ("F2", "A2", "C3")],
    "dramatic": [("D3", "F3", "A3"), ("Bb2", "D3", "F3"), ("F2", "A2", "C3"), ("C3", "E3", "G3")],
    "emotional": [("C3", "E3", "G3"), ("A2", "C3", "E3"), ("D3", "F3", "A3"), ("G2", "B3", "D3")],
}


def music_bed(mood: str, duration: float, seed: int | None = None) -> tuple[Path, str]:
    """Soft royalty-free pad progression, looped to exactly `duration` seconds."""
    mood = mood if mood in _PROGRESSIONS else "adventurous"
    rng = random.Random(seed if seed is not None else random.randint(0, 9_999_999))
    chord_d = 4.0
    progression = _PROGRESSIONS[mood]
    segments: list[Path] = []
    total = 0.0
    i = 0
    while total < duration:
        chord = progression[i % len(progression)]
        i += 1
        seg = _mp3_out(f"music_{mood}")
        cmd = [FFMPEG, "-hide_banner", "-nostdin", "-y"]
        for n in chord:
            cmd += ["-f", "lavfi", "-i", f"sine=frequency={_NOTES[n]}:duration={chord_d}"]
        labels = "".join(f"[{k}:a]" for k in range(3))
        # gentle swelling pad, quiet by default so narration stays on top; soft chime on top
        chime_f = _NOTES[chord[2]] * 2
        cmd += ["-f", "lavfi", "-i", f"sine=frequency={chime_f:.1f}:duration={chord_d/2:.2f}"]
        graph = (
            f"{labels}amix=inputs=3:normalize=0,volume=0.16[pad];"
            f"[3:a]afade=t=in:st=0:d=0.4,afade=t=out:st={chord_d/2-0.6:.2f}:d=0.6,volume=0.05[chime];"
            f"[pad][chime]amix=inputs=2:normalize=0,afade=t=in:st=0:d=0.6,"
            f"afade=t=out:st={chord_d-0.7:.2f}:d=0.7,alimiter=limit=0.9"
        )
        cmd += ["-filter_complex", graph, "-threads", str(FFMPEG_THREADS),
                "-ac", "1", "-ar", str(SR), "-c:a", "libmp3lame", "-q:a", "5", str(seg)]
        _run(cmd)
        segments.append(seg)
        total += chord_d
    # concat looped segments, then trim to exact duration with a closing fade.
    list_file = FX_DIR / f"music_list_{uuid.uuid4().hex[:8]}.txt"
    list_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in segments))
    raw = _mp3_out("music_raw")
    _run([FFMPEG, "-hide_banner", "-nostdin", "-y", "-f", "concat", "-safe", "0",
          "-i", str(list_file), "-c", "copy", str(raw)])
    out = _mp3_out("music_final")
    fade_st = max(0.0, duration - 1.5)
    _run([FFMPEG, "-hide_banner", "-nostdin", "-y", "-i", str(raw),
          "-t", f"{duration:.3f}",
          "-af", f"afade=t=in:st=0:d=1.2,afade=t=out:st={fade_st:.3f}:d=1.5,alimiter=limit=0.9",
          "-threads", str(FFMPEG_THREADS), "-ac", "1", "-ar", str(SR),
          "-c:a", "libmp3lame", "-q:a", "5", str(out)])
    list_file.unlink(missing_ok=True)
    return out, mood


# ---------------------------------------------------------------- final stem mixing

def build_final_audio(
    *,
    scene_stems: list[Path],
    scene_durations: list[float],
    music: Path | None,
    out_path: Path,
    total_duration: float,
    narration_volume: float = 1.0,
    music_volume: float = 0.5,
    sfx_volume: float = 0.7,
    has_narration: bool = True,
) -> Path:
    """Concat per-scene stems (narration+SFX already mixed), then duck music under speech.

    Volumes are 0..1 multipliers of the stem's default level. Music is automatically lowered
    whenever narration plays (sidechain compression) and a limiter prevents clipping.
    """
    # 1. concat scene stems (identical codec params -> stream copy)
    list_file = out_path.parent / f"stem_list_{uuid.uuid4().hex[:8]}.txt"
    list_file.write_text("".join(f"file '{p.as_posix()}'\n" for p in scene_stems))
    voice_track = out_path.parent / f"voice_{uuid.uuid4().hex[:8]}.mp3"
    _run([FFMPEG, "-hide_banner", "-nostdin", "-y", "-f", "concat", "-safe", "0",
          "-i", str(list_file), "-c", "copy", str(voice_track)])
    list_file.unlink(missing_ok=True)

    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-y", "-i", str(voice_track)]
    if music:
        cmd += ["-i", str(music)]
    nv = max(0.0, min(2.0, narration_volume))
    mv = max(0.0, min(2.0, music_volume)) * 0.6  # music defaults well below speech
    if music and has_narration:
        # [1:a]=music main, [0:a]=voice sidechain key → ducked music, then re-mix voice on top.
        # asplit gives the voice two sinks (key input + final mix), since a label is single-use.
        graph = (
            f"[0:a]volume={nv:.2f},asplit=2[vk][vm];"
            f"[1:a]volume={mv:.2f}[m0];"
            f"[m0][vk]sidechaincompress=threshold=0.025:ratio=9:attack=120:release=350:makeup=1[md];"
            f"[md][vm]amix=inputs=2:duration=first:normalize=0,"
            f"apad=whole_dur={total_duration:.3f},atrim=0:{total_duration:.3f},"
            f"afade=t=in:st=0:d=0.4,afade=t=out:st={max(0,total_duration-1.2):.3f}:d=1.2,"
            f"alimiter=limit=0.94[a]"
        )
    elif music:
        graph = (
            f"[1:a]volume={mv:.2f}[m];"
            f"[m][0:a]amix=inputs=2:duration=first:normalize=0,"
            f"apad=whole_dur={total_duration:.3f},atrim=0:{total_duration:.3f},"
            f"afade=t=in:st=0:d=0.4,afade=t=out:st={max(0,total_duration-1.2):.3f}:d=1.2,"
            f"alimiter=limit=0.94[a]"
        )
    else:
        graph = (
            f"[0:a]volume={nv:.2f},apad=whole_dur={total_duration:.3f},"
            f"atrim=0:{total_duration:.3f},"
            f"afade=t=in:st=0:d=0.4,afade=t=out:st={max(0,total_duration-1.2):.3f}:d=1.2,"
            f"alimiter=limit=0.94[a]"
        )
    cmd += ["-filter_complex", graph, "-map", "[a]",
            "-threads", str(FFMPEG_THREADS), "-ac", "1", "-ar", str(SR),
            "-c:a", "libmp3lame", "-q:a", "4", str(out_path)]
    _run(cmd, timeout=300)
    voice_track.unlink(missing_ok=True)
    return out_path


def mix_scene_stem(narration: Path | None, sfx: Path | None, out_path: Path,
                   duration: float, narration_volume: float, sfx_volume: float) -> Path:
    """One scene's bed: SFX bed plus optional narration, trimmed exactly to scene length."""
    if narration and sfx:
        _mix([(sfx, duration), (narration, duration)], out_path, duration,
             weights=[max(0.0, sfx_volume) * 0.8, max(0.0, min(2.0, narration_volume))])
    elif narration:
        _mix([(narration, duration)], out_path, duration, weights=[narration_volume])
    elif sfx:
        _mix([(sfx, duration)], out_path, duration, weights=[sfx_volume * 0.8])
    else:
        _lavfi(f"anullsrc=r={SR}:cl=mono", out_path, duration)
    return out_path
