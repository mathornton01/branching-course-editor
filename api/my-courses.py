"""
/api/my-courses — Per-user course list.

GET /api/my-courses
    Authorization: Bearer <token>

Returns every course in course_content that belongs to the authenticated user.
If no token is provided, returns an empty list with 200 OK so the frontend
can render consistently.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _cors(h):
    h.send_header("Access-Control-Allow-Origin", "*")
    h.send_header("Access-Control-Allow-Methods", "GET,OPTIONS")
    h.send_header("Access-Control-Allow-Headers", "*")


def _json(h, status, data):
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    _cors(h)
    h.end_headers()
    h.wfile.write(json.dumps(data).encode())


def _bearer_token(handler):
    auth = handler.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _user_from_token(supabase, token):
    if not token:
        return None
    try:
        result = supabase.table("auth_tokens").select(
            "*, users!auth_tokens_user_id_fkey(id, email, username, role, display_name)"
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
    return row.get("users") or {"id": row.get("user_id")}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        token = _bearer_token(self)
        try:
            from lib.supabase_client import get_supabase
            supabase = get_supabase()
        except RuntimeError:
            _json(self, 200, {"courses": [], "count": 0, "reason": "supabase-not-configured"})
            return
        except Exception as e:
            _json(self, 500, {"error": str(e)})
            return

        user = _user_from_token(supabase, token)
        if not user:
            _json(self, 200, {"courses": [], "count": 0, "reason": "unauthenticated"})
            return

        try:
            result = supabase.table("course_content").select(
                "id,title,description,topic,theme,difficulty,estimated_minutes,tags,user_id,updated_at,created_at"
            ).eq("user_id", user["id"]).order("updated_at", desc=True).execute()
            rows = result.data or []
            for r in rows:
                r["source"] = "user"
                r.setdefault("node_count", 0)
            _json(self, 200, {
                "courses": rows,
                "count": len(rows),
                "user_id": user["id"],
            })
        except Exception as e:
            _json(self, 500, {"error": str(e)})

    def do_OPTIONS(self):
        self.send_response(204)
        _cors(self)
        self.end_headers()
