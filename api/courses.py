"""
/api/courses - Vercel serverless function for course listing.

Returns the combined catalog of:
  1. Static seed courses (387 JSON files bundled as _catalog.json)
  2. User-created courses saved in Supabase table course_content

GET /api/courses
    -> { courses: [...], generated: N, static_count, user_count }

Individual course GET/PUT/DELETE lives in api/courses/[id].py
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _cors(h):
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "*")


def _json_response(h, status, data):
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    _cors(h)
    h.end_headers()
    h.wfile.write(json.dumps(data).encode())


# Load the static catalog at cold start.
_STATIC_CATALOG = None


def _load_static_catalog():
    global _STATIC_CATALOG
    if _STATIC_CATALOG is not None:
        return _STATIC_CATALOG
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_catalog.json")
    try:
        with open(path, "r") as fp:
            _STATIC_CATALOG = json.load(fp).get("courses", [])
    except Exception:
        _STATIC_CATALOG = []
    return _STATIC_CATALOG


def _load_user_courses():
    """Fetch user-created courses from Supabase. Returns [] if not configured."""
    try:
        from lib.supabase_client import get_supabase
        supabase = get_supabase()
        result = supabase.table("course_content").select(
            "id,title,description,topic,theme,difficulty,estimated_minutes,tags,user_id,updated_at"
        ).order("updated_at", desc=True).execute()
        rows = result.data or []
        for r in rows:
            r["source"] = "user"
            r.setdefault("node_count", 0)
        return rows
    except Exception:
        return []


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        static_courses = _load_static_catalog()
        user_courses = _load_user_courses()

        # User courses override static ones with the same id.
        user_ids = {c["id"] for c in user_courses}
        merged = [c for c in static_courses if c["id"] not in user_ids] + user_courses

        _json_response(self, 200, {
            "courses": merged,
            "generated": len(merged),
            "static_count": len(static_courses),
            "user_count": len(user_courses),
        })

    def do_POST(self):
        """Create a new user course. Editor usually uses PUT /api/courses/<id>."""
        try:
            from lib.supabase_client import get_supabase
            supabase = get_supabase()

            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}

            cid = body.get("id")
            if not cid:
                _json_response(self, 400, {"error": "course id is required"})
                return

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
            if body.get("user_id"):
                record["user_id"] = body["user_id"]

            result = supabase.table("course_content").upsert(record).execute()
            _json_response(self, 201, {"course": result.data[0] if result.data else record})
        except RuntimeError:
            _json_response(self, 503, {"error": "Supabase not configured"})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def do_OPTIONS(self):
        self.send_response(204)
        _cors(self)
        self.end_headers()
