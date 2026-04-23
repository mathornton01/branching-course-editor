"""
/api/course - Vercel serverless function for individual course operations.

Handles:
  GET    /api/course?id=<course_id>  -> get store metadata for a course
  PUT    /api/course?id=<course_id>  -> update store metadata
  DELETE /api/course?id=<course_id>  -> remove from store catalog

Note: The actual course JSON content is served statically from /courses/<id>.json.
This endpoint only manages the database metadata (pricing, ratings, etc.).
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _cors_headers(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET,PUT,DELETE,OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "*")


def _json_response(handler, status, data):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    _cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(json.dumps(data).encode())


def _get_course_id(handler):
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(handler.path)
    params = parse_qs(parsed.query)
    return params.get("id", [None])[0]


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Get store metadata for a specific course."""
        course_id = _get_course_id(self)
        if not course_id:
            _json_response(self, 400, {"error": "id query parameter is required"})
            return

        try:
            from lib.supabase_client import get_supabase
            supabase = get_supabase()

            result = supabase.table("courses_store").select(
                "*, users!courses_store_instructor_id_fkey(display_name)"
            ).eq("course_id", course_id).single().execute()

            _json_response(self, 200, {"course": result.data})
        except RuntimeError:
            _json_response(self, 503, {"error": "Supabase not configured"})
        except Exception as e:
            if "No rows" in str(e) or "0 rows" in str(e):
                _json_response(self, 404, {"error": f"Course {course_id} not found in store"})
            else:
                _json_response(self, 500, {"error": str(e)})

    def do_PUT(self):
        """Update store metadata for a course."""
        course_id = _get_course_id(self)
        if not course_id:
            _json_response(self, 400, {"error": "id query parameter is required"})
            return

        try:
            from lib.supabase_client import get_supabase
            supabase = get_supabase()

            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length)) if content_length else {}

            # Only allow updating specific fields
            allowed = ["price_cents", "currency", "category", "is_published",
                        "is_featured", "preview_nodes", "instructor_id"]
            updates = {k: v for k, v in body.items() if k in allowed}

            if not updates:
                _json_response(self, 400, {"error": "No valid fields to update"})
                return

            result = supabase.table("courses_store").update(updates).eq(
                "course_id", course_id
            ).execute()

            _json_response(self, 200, {"course": result.data[0] if result.data else updates})
        except RuntimeError:
            _json_response(self, 503, {"error": "Supabase not configured"})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def do_DELETE(self):
        """Remove a course from the store catalog."""
        course_id = _get_course_id(self)
        if not course_id:
            _json_response(self, 400, {"error": "id query parameter is required"})
            return

        try:
            from lib.supabase_client import get_supabase
            supabase = get_supabase()

            supabase.table("courses_store").delete().eq(
                "course_id", course_id
            ).execute()

            _json_response(self, 200, {"deleted": course_id})
        except RuntimeError:
            _json_response(self, 503, {"error": "Supabase not configured"})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def do_OPTIONS(self):
        self.send_response(204)
        _cors_headers(self)
        self.end_headers()
