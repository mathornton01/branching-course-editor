"""
/api/courses/<id> - Vercel dynamic route for a single course.

GET    /api/courses/<id>   -> course JSON (Supabase user course > static seed file)
PUT    /api/courses/<id>   -> save/upsert course to Supabase course_content
DELETE /api/courses/<id>   -> delete user course from Supabase

Static seed courses (public/courses/*.json) are read-only fallbacks.
User edits are always persisted to Supabase. If the request carries an
Authorization: Bearer <token> header, the upsert is stamped with the
authenticated user_id so /api/my-courses can list "your" courses.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

# Add the project root (two levels up from api/courses/) so lib/ is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _cors(h):
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Access-Control-Allow-Methods", "GET,PUT,DELETE,OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "*")


def _json_response(h, status, data):
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    _cors(h)
    h.end_headers()
    h.wfile.write(json.dumps(data).encode())


def _course_id_from_path(path):
    """Extract <id> from /api/courses/<id>."""
    parsed = urlparse(path).path.rstrip("/")
    parts = parsed.split("/")
    return parts[-1] if parts else None


def _bearer_token(handler):
    auth = handler.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _user_id_from_token(supabase, token):
    if not token:
        return None
    try:
        result = supabase.table("auth_tokens").select(
            "user_id,expires_at"
        ).eq("token", token).limit(1).execute()
    except Exception:
        return None
    if not result.data:
        return None
    row = result.data[0]
    exp = row.get("expires_at")
    if exp:
        try:
            if datetime.fromisoformat(exp.replace("Z", "+00:00")) < datetime.now(timezone.utc):
                return None
        except Exception:
            pass
    return row.get("user_id")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        cid = _course_id_from_path(self.path)
        if not cid:
            _json_response(self, 400, {"error": "missing course id"})
            return

        # Try Supabase user courses. Static seed courses are served directly by
        # the CDN at /courses/<id>.json; the frontend falls back to that on 404.
        try:
            from lib.supabase_client import get_supabase
            supabase = get_supabase()
            result = supabase.table("course_content").select("content").eq("id", cid).limit(1).execute()
            if result.data:
                _json_response(self, 200, result.data[0]["content"])
                return
        except RuntimeError:
            pass  # Supabase not configured
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})
            return

        _json_response(self, 404, {"error": f"course {cid} not in user storage — try /courses/{cid}.json"})

    def do_PUT(self):
        cid = _course_id_from_path(self.path)
        if not cid:
            _json_response(self, 400, {"error": "missing course id"})
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length)) if length else {}
        except json.JSONDecodeError as e:
            _json_response(self, 400, {"error": f"invalid JSON: {e}"})
            return

        # Ensure the body's id matches the URL
        body["id"] = cid
        token = _bearer_token(self)

        try:
            from lib.supabase_client import get_supabase
            supabase = get_supabase()

            # Stamp with authenticated user when available.
            user_id = _user_id_from_token(supabase, token) or body.get("user_id")

            record = {
                "id": cid,
                "title": body.get("title") or cid,
                "description": body.get("description") or "",
                "topic": body.get("topic") or "",
                "theme": body.get("theme") or "",
                "difficulty": body.get("difficulty") or "beginner",
                "estimated_minutes": body.get("estimated_minutes") or 0,
                "tags": body.get("tags") or [],
                "content": body,
            }
            if user_id:
                record["user_id"] = user_id
                body["user_id"] = user_id  # echo into the stored content too

            supabase.table("course_content").upsert(record).execute()
            _json_response(self, 200, {"saved": True, "id": cid, "user_id": user_id})
        except RuntimeError:
            _json_response(self, 503, {"error": "Supabase not configured — cannot save"})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def do_DELETE(self):
        cid = _course_id_from_path(self.path)
        if not cid:
            _json_response(self, 400, {"error": "missing course id"})
            return
        token = _bearer_token(self)
        try:
            from lib.supabase_client import get_supabase
            supabase = get_supabase()

            # Only allow deletion of the caller's own courses (when authed).
            user_id = _user_id_from_token(supabase, token)
            q = supabase.table("course_content").delete().eq("id", cid)
            if user_id:
                q = q.eq("user_id", user_id)
            q.execute()
            _json_response(self, 200, {"deleted": cid})
        except RuntimeError:
            _json_response(self, 503, {"error": "Supabase not configured"})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def do_OPTIONS(self):
        self.send_response(204)
        _cors(self)
        self.end_headers()
