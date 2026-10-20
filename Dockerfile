# StoryForge AI — single-container deployment (free hosts: Hugging Face Spaces, Render,
# Fly.io, a Raspberry Pi / home server, or any Docker host).
# UI + API are served together on $PORT (defaults to 7860 for Hugging Face Spaces).

# ---------- Stage 1: build the React frontend ----------
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# ---------- Stage 1b: build the VoiceForge voice-studio app (served at /voice/) ----------
FROM node:20-slim AS voicestudio
WORKDIR /app/voice-studio
COPY voice-studio/package*.json ./
RUN npm ci || npm install
COPY voice-studio/ ./
RUN npm run build

# ---------- Stage 2: Python runtime ----------
FROM python:3.12-slim-bookworm

# ffmpeg: video rendering · fonts-dejavu-core: subtitles & title cards
# libgomp1: required by the onnxruntime engine inside Piper TTS · curl: health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
        fontconfig \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies first (better layer caching)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r backend/requirements.txt

# Backend code, built frontend, and the offline Piper voice (downloaded at build time so
# the source repository itself stays small).
COPY backend/ ./backend/
COPY --from=frontend /app/frontend/dist ./frontend/dist
COPY --from=voicestudio /app/voice-studio/dist ./frontend/dist/voice

# Free local neural TTS voice (~63 MB, pulled once during the image build).
RUN mkdir -p backend/voices \
    && curl -fL --retry 3 -o backend/voices/en_US-amy-low.onnx \
       https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/low/en_US-amy-low.onnx \
    && curl -fL --retry 3 -o backend/voices/en_US-amy-low.onnx.json \
       https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/low/en_US-amy-low.onnx.json

# All generated data lives here; mount a volume to persist projects between restarts.
# Memory-safe defaults for small containers (512 MB free tiers): TTS runs in a child
# process, FFmpeg uses one thread, and glibc malloc arenas are capped. Override with -e
# on bigger hosts (e.g. STORYFORGE_FFMPEG_THREADS=4).
ENV STORYFORGE_DATA=/app/data \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    STORYFORGE_TTS_SUBPROCESS=1 \
    STORYFORGE_FFMPEG_THREADS=1 \
    MALLOC_ARENA_MAX=2

RUN mkdir -p /app/data && chmod 777 /app/data
VOLUME ["/app/data"]
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

WORKDIR /app/backend
# Render/Fly inject $PORT; HF Spaces expects 7860; local docker run can override with -e PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
