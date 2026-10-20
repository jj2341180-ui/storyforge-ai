"""SQLite persistence for projects and background jobs (local-first, no server DB needed)."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from typing import Any

from .config import DB_PATH


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mode TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL NOT NULL DEFAULT 0,
                message TEXT DEFAULT '',
                result TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )"""
        )


# ---------------- projects ----------------

def list_projects() -> list[dict[str, Any]]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    out = []
    for r in rows:
        d = json.loads(r["data"])
        out.append(
            {
                "id": r["id"],
                "name": r["name"],
                "mode": r["mode"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "exports": d.get("exports", []),
                "scene_count": len(d.get("scenes", [])),
            }
        )
    return out


def save_project(project: dict[str, Any]) -> dict[str, Any]:
    now = time.time()
    pid = project.get("id") or str(uuid.uuid4())
    project["id"] = pid
    project.setdefault("created_at", now)
    project["updated_at"] = now
    with _conn() as c:
        c.execute(
            """INSERT INTO projects(id,name,mode,data,created_at,updated_at) VALUES(?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET name=?,mode=?,data=?,updated_at=?""",
            (
                pid,
                project.get("name", "Untitled"),
                project.get("mode", "story"),
                json.dumps(project),
                project["created_at"],
                now,
                project.get("name", "Untitled"),
                project.get("mode", "story"),
                json.dumps(project),
                now,
            ),
        )
    return project


def get_project(pid: str) -> dict[str, Any] | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    return json.loads(r["data"]) if r else None


def delete_project(pid: str) -> bool:
    with _conn() as c:
        cur = c.execute("DELETE FROM projects WHERE id=?", (pid,))
    return cur.rowcount > 0


# ---------------- jobs ----------------

def create_job(project_id: str, kind: str) -> dict[str, Any]:
    now = time.time()
    job = {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "kind": kind,
        "status": "queued",
        "progress": 0.0,
        "message": "",
        "result": "",
        "created_at": now,
        "updated_at": now,
    }
    with _conn() as c:
        c.execute(
            "INSERT INTO jobs(id,project_id,kind,status,progress,message,result,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (job["id"], project_id, kind, job["status"], 0.0, "", "", now, now),
        )
    return job


def update_job(jid: str, **fields: Any) -> None:
    fields["updated_at"] = time.time()
    keys = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [jid]
    with _conn() as c:
        c.execute(f"UPDATE jobs SET {keys} WHERE id=?", vals)


def reset_stale_jobs(message: str = "Interrupted by a server restart or update - please render again.") -> int:
    """Mark every unfinished job as failed. Called at startup: a job left 'running' when the
    process died (OOM kill, redeploy, crash) can never resume, so it must not fake progress."""
    now = time.time()
    with _conn() as c:
        cur = c.execute(
            "UPDATE jobs SET status='failed', message=?, updated_at=? "
            "WHERE status IN ('queued','running','finalizing')",
            (message, now),
        )
    return cur.rowcount


def get_job(jid: str) -> dict[str, Any] | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["result"] = json.loads(d["result"]) if d["result"] else None
    return d


def list_jobs(project_id: str | None = None) -> list[dict[str, Any]]:
    with _conn() as c:
        if project_id:
            rows = c.execute(
                "SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC", (project_id,)
            ).fetchall()
        else:
            rows = c.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["result"] = json.loads(d["result"]) if d["result"] else None
        out.append(d)
    return out
