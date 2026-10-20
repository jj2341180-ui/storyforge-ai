"""End-to-end backend smoke test: story idea -> script -> storyboard -> TTS -> MP4 render."""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(method: str, path: str, body=None, raw=False):
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            payload = r.read()
            return payload if raw else json.loads(payload)
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:600])
        raise


def main() -> None:
    print("1/10 health:", call("GET", "/api/health"))
    print("2/10 providers:", json.dumps(call("GET", "/api/providers/status")["hardware"]))
    voices = call("GET", "/api/tts/voices")["voices"]
    assert voices, "no TTS voices installed"
    print("3/10 TTS voices:", [v["id"] for v in voices])

    project = call("POST", "/api/projects", {"name": "E2E Dragon Kingdom", "mode": "story"})
    pid = project["id"]
    print("4/10 project:", pid)

    settings = {**project["settings"], "category": "fantasy", "sceneCount": 4, "tone": "epic",
                "ending": "mysterious", "length": 1}
    pack = call("POST", "/api/studio/generate-script", {"settings": settings})
    print("5/10 script:", pack["title"], "| est", pack["estimated_seconds"], "s | warning:",
          bool(pack["duration_warning"]))

    project["settings"] = settings
    project["script"] = {"title": pack["title"], "logline": pack["logline"],
                         "originality": pack["originality"]}
    project["scenes"] = pack["scenes"]
    project["characters"] = pack["characters"]
    project["style"] = pack["style"]
    project["narration_voice"] = voices[0]["id"]
    call("PUT", f"/api/projects/{pid}", project)

    for sc in project["scenes"]:
        asset = call("POST", f"/api/projects/{pid}/placeholders/{sc['id']}")
        print("   placeholder:", asset["name"][:50])
    print("6/10 placeholders done")

    for sc in project["scenes"]:
        out = call("POST", f"/api/projects/{pid}/tts",
                   {"scene_id": sc["id"], "text": sc["narration"],
                    "voice_id": voices[0]["id"], "speed": 1.0, "kind": "narration"})
        print("   tts:", round(out["duration"], 2), "s")
    print("7/10 narration done")

    job = call("POST", f"/api/projects/{pid}/render")
    print("8/10 render job:", job["id"])
    while True:
        j = call("GET", f"/api/jobs/{job['id']}")
        print(f"   {j['status']} {j['progress']*100:.0f}% {j['message'][:70]}")
        if j["status"] in ("done", "failed"):
            break
        time.sleep(2)
    assert j["status"] == "done", j["message"]
    result = j["result"]
    print("9/10 MP4:", result["width"], "x", result["height"], result["duration"], "s ->",
          result["file"].split("/")[-1])

    meta = call("GET", f"/api/projects/{pid}/metadata")
    print("10/10 metadata titles:", meta["title_options"])
    thumb = call("POST", f"/api/projects/{pid}/thumbnail",
                 {"title": pack["title"], "placement": "bottom", "aspect": "16:9"})
    print("   thumbnail:", thumb["path"].split("/")[-1])
    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
