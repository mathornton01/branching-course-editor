"""
/api/courses - Vercel serverless function.

HYBRID APPROACH:
- Course JSON files are served statically from public/courses/
- This endpoint handles database operations:
  GET  /api/courses  -> list store metadata (prices, ratings, etc.) from Supabase
  POST /api/courses  -> save a new course to the store catalog in Supabase
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys

# Add parent dir to path for lib imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _cors_headers(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "*")


def _json_response(handler, status, data):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    _cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(json.dumps(data).encode())


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """List published courses from Supabase with store metadata."""
        try:
            from lib.supabase_client import get_supabase
            supabase = get_supabase()

            # Parse query params from path
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            category = params.get("category", [None])[0]
            search = params.get("search", [None])[0]
            sort = params.get("sort", ["popular"])[0]
            page = int(params.get("page", [1])[0])
            per_page = int(params.get("per_page", [24])[0])

            query = supabase.table("courses_store").select(
                "*, users!courses_store_instructor_id_fkey(display_name)"
            ).eq("is_published", True)

            if category:
                query = query.eq("category", category)
            if search:
                query = query.or_(f"course_id.ilike.%{search}%,category.ilike.%{search}%")

            sort_map = {
                "popular": ("total_purchases", {"ascending": False}),
                "newest": ("published_at", {"ascending": False}),
                "price_asc": ("price_cents", {"ascending": True}),
                "price_desc": ("price_cents", {"ascending": False}),
                "rating": ("avg_rating", {"ascending": False}),
            }
            sort_col, sort_opts = sort_map.get(sort, sort_map["popular"])
            query = query.order(sort_col, **sort_opts)

            offset = (page - 1) * per_page
            query = query.range(offset, offset + per_page - 1)

            result = query.execute()

            _json_response(self, 200, {
                "courses": result.data,
                "page": page,
                "per_page": per_page,
            })
        except RuntimeError:
            # Supabase not configured yet - return empty list
            _json_response(self, 200, {
                "courses": [],
                "page": 1,
                "per_page": 24,
                "note": "Supabase not configured. Course JSON files are available at /courses/"
            })
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def do_POST(self):
        """Create or update a course in the store catalog."""
        try:
            from lib.supabase_client import get_supabase
            supabase = get_supabase()

            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length)) if content_length else {}

            course_id = body.get("course_id")
            if not course_id:
                _json_response(self, 400, {"error": "course_id is required"})
                return

            record = {
                "course_id": course_id,
                "price_cents": body.get("price_cents", 0),
                "currency": body.get("currency", "USD"),
                "category": body.get("category"),
                "is_published": body.get("is_published", False),
                "is_featured": body.get("is_featured", False),
                "preview_nodes": body.get("preview_nodes", 3),
            }
            if body.get("instructor_id"):
                record["instructor_id"] = body["instructor_id"]

            result = supabase.table("courses_store").upsert(record).execute()
            _json_response(self, 201, {"course": result.data[0] if result.data else record})
        except RuntimeError:
            _json_response(self, 503, {"error": "Supabase not configured"})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def do_OPTIONS(self):
        self.send_response(204)
        _cors_headers(self)
        self.end_headers()
