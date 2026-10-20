"""Verify compact placeholders, chunked captions, scene-count fix and a 9:16 Shorts render."""
import json
import time
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:400])
        raise


p = call("POST", "/api/projects", {"name": "Verify Shorts", "mode": "story"})
pid = p["id"]
pack = call("POST", "/api/studio/generate-script",
            {"settings": {**p["settings"], "category": "fantasy", "sceneCount": 3, "length": 1}})
assert len(pack["scenes"]) == 3, len(pack["scenes"])
headings = [s["heading"] for s in pack["scenes"]]
print("scene headings:", headings)
assert headings[-1].endswith("What Remains"), headings

p["scenes"] = pack["scenes"]
p["script"] = {"title": pack["title"], "logline": pack["logline"], "originality": pack["originality"]}
p["style"] = pack["style"]
p["characters"] = pack["characters"]
p["timeline"].update({"aspect": "9:16", "resolution": "720p", "outro": True, "burn_captions": True})
for s in p["scenes"]:
    s["duration"] = 4.0
call("PUT", f"/api/projects/{pid}", p)

for s in pack["scenes"]:
    call("POST", f"/api/projects/{pid}/placeholders/{s['id']}")
print("placeholders created")

job = call("POST", f"/api/projects/{pid}/render")
while True:
    j = call("GET", f"/api/jobs/{job['id']}")
    if j["status"] in ("done", "failed"):
        break
    time.sleep(1.5)
assert j["status"] == "done", j["message"]
res = j["result"]
print("render:", res["width"], "x", res["height"], res["duration"], "s | placeholders:",
      len(res["used_placeholders"]), "| captions:", res["captions_burned"])
assert (res["width"], res["height"]) == (720, 1280)
print("VERIFY PASSED:", res["file"])
