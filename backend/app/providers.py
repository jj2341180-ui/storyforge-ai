"""
Pluggable model providers for text-to-video / image-to-video / image generation.

Every provider is OPTIONAL and disabled by default. Nothing here calls a paid API.
The UI uses status() to show exactly what is configured, what hardware is missing,
and which free alternative (Mode B image-based workflow) to use instead.

Configure local providers with environment variables (see SETUP.md):
  STORYFORGE_COMFY_URL   e.g. http://127.0.0.1:8188   (ComfyUI with SVD / AnimateDiff / CogVideo nodes)
  STORYFORGE_A1111_URL   e.g. http://127.0.0.1:7860   (Automatic1111 / Forge / SD.Next)
  STORYFORGE_VIDEO_CMD   command template containing {prompt} {out} (local video CLI)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from typing import Any

from .config import A1111_URL, COMFYUI_URL, VIDEO_CLI_CMD


# ---------------- hardware inspection ----------------

def hardware_status() -> dict[str, Any]:
    import multiprocessing

    try:
        import psutil  # type: ignore
        ram_gb = round(psutil.virtual_memory().total / 1e9, 1)
    except Exception:
        try:
            with open("/proc/meminfo") as f:
                mem_kb = int(next(l for l in f if l.startswith("MemTotal")).split()[1])
            ram_gb = round(mem_kb / 1e6, 1)
        except Exception:
            ram_gb = 0.0

    gpu = {"name": None, "vram_gb": None, "driver": False}
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total",
                                  "--format=csv,noheader"], capture_output=True, text=True, timeout=10)
            if out.returncode == 0 and out.stdout.strip():
                parts = out.stdout.strip().split(",")
                gpu["name"] = parts[0].strip()
                gpu["vram_gb"] = parts[1].strip().split()[0]
                gpu["driver"] = True
        except Exception:
            pass

    disk = shutil.disk_usage(os.path.expanduser("~"))
    return {
        "cpu_cores": multiprocessing.cpu_count(),
        "ram_gb": ram_gb,
        "gpu": gpu,
        "disk_free_gb": round(disk.free / 1e9, 1),
        "can_run_local_video": bool(gpu["driver"] and gpu["vram_gb"] and float(gpu["vram_gb"]) >= 8),
        "note": (
            "Local video diffusion models (e.g. SVD, AnimateDiff, CogVideo) realistically need an NVIDIA GPU "
            "with 8-24 GB VRAM and 16+ GB system RAM. CPU-only generation is technically possible with some "
            "models but can take hours per clip. Without suitable hardware, use Mode B's image-based workflow."
        ),
    }


def _http_ok(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= r.status < 500
    except Exception:
        return False


# ---------------- provider registry ----------------

class BaseProvider:
    id: str = "base"
    name: str = "Base"
    kind: str = "t2v"            # t2v | i2v | image
    requires: str = ""
    docs: str = ""

    def configured(self) -> bool:
        raise NotImplementedError

    def status(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "kind": self.kind,
            "configured": self.configured(), "requires": self.requires,
            "docs": self.docs, "cost": "Free / open source, runs on your own hardware",
            # Every adapter is always selectable in the UI; selecting an unconfigured one
            # returns its setup instructions instead of pretending generation succeeded.
            "selectable": True,
        }

    def generate(self, prompt: str, out_path: str, **opts: Any) -> str:
        raise RuntimeError(f"{self.name} is not configured. {self.requires}")


class ComfyUIProvider(BaseProvider):
    id = "comfyui"
    name = "ComfyUI (local) - LTX-Video / Wan / SVD / AnimateDiff nodes"
    kind = "t2v"
    requires = (
        "A running local ComfyUI server (set STORYFORGE_COMFY_URL) with a free open-weights video "
        "model such as LTX-Video 2B (~8 GB VRAM), Wan 2.1, Stable Video Diffusion (image-to-video) "
        "or AnimateDiff, plus an API workflow file (set STORYFORGE_COMFY_WORKFLOW)."
    )
    docs = "https://github.com/comfyanonymous/ComfyUI"

    def configured(self) -> bool:
        return bool(COMFYUI_URL) and _http_ok(COMFYUI_URL.rstrip("/") + "/system_stats")

    def _base(self) -> str:
        return COMFYUI_URL.rstrip("/")

    def _upload_image(self, image_path: str) -> str:
        """Upload a reference frame for image-to-video workflows. Returns the server filename."""
        import uuid as _uuid
        boundary = "----storyforge" + _uuid.uuid4().hex
        filename = os.path.basename(image_path)
        with open(image_path, "rb") as fh:
            blob = fh.read()
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + blob + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            self._base() + "/upload/image", data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())["name"]

    def generate(self, prompt: str, out_path: str, **opts: Any) -> str:
        """Queue a workflow and block until its output video is downloaded to out_path.

        Supported opts: workflow_json (required, API-format dict supporting {prompt} {seed}
        {frames} {fps} {duration} {image} placeholders), reference_image (local path for I2V),
        seed, duration, poll_timeout.
        """
        if not self.configured():
            raise RuntimeError(self.requires)
        workflow = opts.get("workflow_json")
        if not workflow:
            raise RuntimeError(
                "ComfyUI is reachable but no workflow JSON was supplied. Export an LTX-Video/Wan/SVD "
                "API workflow from ComfyUI (use the {prompt}/{seed}/{frames} placeholders) and point "
                "STORYFORGE_COMFY_WORKFLOW at it."
            )
        reference = opts.get("reference_image") or ""
        uploaded = ""
        if reference and os.path.exists(reference):
            uploaded = self._upload_image(reference)

        prompt_id = self._queue(workflow)
        timeout = float(opts.get("poll_timeout", 1800))
        outputs = self._wait_for_outputs(prompt_id, timeout)
        if not outputs:
            raise RuntimeError("ComfyUI finished but produced no video output.")
        # Prefer a real video; accept GIF only as a last resort.
        video = next((o for o in outputs if o["filename"].lower().endswith((".mp4", ".webm", ".mkv"))),
                     outputs[0])
        self._download_output(video, out_path)
        return out_path

    def _queue(self, workflow: dict[str, Any]) -> str:
        req = urllib.request.Request(
            self._base() + "/prompt",
            data=json.dumps({"prompt": workflow}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI rejected the workflow: {str(data)[:300]}")
        return prompt_id

    def _wait_for_outputs(self, prompt_id: str, timeout: float) -> list[dict[str, str]]:
        import time as _time
        deadline = _time.monotonic() + timeout
        while _time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(self._base() + f"/history/{prompt_id}", timeout=30) as r:
                    history = json.loads(r.read())
            except Exception:
                history = {}
            entry = history.get(prompt_id)
            if entry:
                outputs: list[dict[str, str]] = []
                for node_out in entry.get("outputs", {}).values():
                    for key in ("videos", "gifs", "images"):
                        for item in node_out.get(key, []) or []:
                            if isinstance(item, dict) and item.get("filename"):
                                outputs.append(item)
                if outputs:
                    return outputs
                status = entry.get("status", {})
                if status.get("completed") is False and status.get("status_str") == "error":
                    raise RuntimeError("ComfyUI reported a workflow execution error.")
            _time.sleep(3)
        raise TimeoutError(f"Timed out after {timeout:.0f}s waiting for ComfyUI to finish.")

    def _download_output(self, item: dict[str, str], out_path: str) -> None:
        import urllib.parse as _parse
        qs = _parse.urlencode({k: item[k] for k in ("filename", "subfolder", "type") if item.get(k)})
        url = self._base() + "/view?" + qs
        with urllib.request.urlopen(url, timeout=300) as r, open(out_path, "wb") as fh:
            shutil.copyfileobj(r, fh)
        if not os.path.exists(out_path) or os.path.getsize(out_path) < 1024:
            raise RuntimeError("Downloaded ComfyUI output was empty.")


class A1111Provider(BaseProvider):
    id = "a1111"
    name = "Automatic1111 / Forge / SD.Next (local image model)"
    kind = "image"
    requires = "A running local Stable Diffusion WebUI API; set STORYFORGE_A1111_URL. 4-8 GB VRAM."
    docs = "https://github.com/AUTOMATIC1111/stable-diffusion-webui"

    def configured(self) -> bool:
        return bool(A1111_URL) and _http_ok(A1111_URL.rstrip("/") + "/sdapi/v1/options")

    def generate(self, prompt: str, out_path: str, **opts: Any) -> str:
        if not self.configured():
            raise RuntimeError(self.requires)
        payload = {
            "prompt": prompt,
            "negative_prompt": opts.get("negative_prompt", ""),
            "width": opts.get("width", 1024),
            "height": opts.get("height", 576),
            "steps": opts.get("steps", 20),
        }
        req = urllib.request.Request(
            A1111_URL.rstrip("/") + "/sdapi/v1/txt2img",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            import base64
            data = json.loads(r.read())
        img_b64 = data["images"][0].split(",", 1)[0]
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(img_b64))
        return out_path


class GenericCLIProvider(BaseProvider):
    id = "cli"
    name = "Generic local video CLI (CogVideo / custom wrapper)"
    kind = "t2v"
    requires = "Set STORYFORGE_VIDEO_CMD to a command template using {prompt}, {out} and optionally {image}."
    docs = ""

    def configured(self) -> bool:
        return bool(VIDEO_CLI_CMD)

    def generate(self, prompt: str, out_path: str, **opts: Any) -> str:
        if not self.configured():
            raise RuntimeError(self.requires)
        cmd = VIDEO_CLI_CMD.format(prompt=prompt.replace('"', "'"), out=out_path,
                                   image=opts.get("reference_image", "") or "")
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=7200)
        if proc.returncode != 0 or not os.path.exists(out_path):
            raise RuntimeError(f"CLI provider failed: {proc.stderr[-500:]}")
        return out_path


PROVIDERS = [ComfyUIProvider(), A1111Provider(), GenericCLIProvider()]

# Planning selector for Mode A hardware requirements (workstation-class local video setups).
RAM_OPTIONS_GB = [32, 40, 48, 56, 64, 72]


def provider_status() -> dict[str, Any]:
    return {
        "hardware": hardware_status(),
        "providers": [p.status() for p in PROVIDERS],
        "ram_options_gb": RAM_OPTIONS_GB,
        "any_configured": any(p.configured() for p in PROVIDERS),
        "honest_alternative": (
            "No video model is configured or this machine cannot run one. StoryForge still produces "
            "complete MP4 videos via Mode B: original script, local Piper narration, licensed/uploaded "
            "images (or labeled placeholders), Ken Burns motion, transitions, captions and music."
        ),
    }


def get_provider(pid: str) -> BaseProvider | None:
    return next((p for p in PROVIDERS if p.id == pid), None)
