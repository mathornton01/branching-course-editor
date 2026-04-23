"""
/api/auth - Vercel serverless function for authentication.

Handles:
  POST /api/auth?action=login     -> authenticate user, return token
  POST /api/auth?action=register  -> create new user account
  POST /api/auth?action=validate  -> validate an existing token
"""

from http.server import BaseHTTPRequestHandler
import json
import hashlib
import secrets
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _cors_headers(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "POST,OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "*")


def _json_response(handler, status, data):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    _cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(json.dumps(data).encode())


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 100000
    ).hex()


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        action = params.get("action", [None])[0]

        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        if action == "login":
            self._handle_login(body)
        elif action == "register":
            self._handle_register(body)
        elif action == "validate":
            self._handle_validate(body)
        else:
            _json_response(self, 400, {
                "error": "Invalid action. Use ?action=login, ?action=register, or ?action=validate"
            })

    def _handle_login(self, body):
        email_or_username = body.get("email") or body.get("username")
        password = body.get("password")

        if not email_or_username or not password:
            _json_response(self, 400, {"error": "email/username and password are required"})
            return

        try:
            from lib.supabase_client import get_supabase
            supabase = get_supabase()

            # Find user by email or username
            result = supabase.table("users").select("*").or_(
                f"email.eq.{email_or_username},username.eq.{email_or_username}"
            ).execute()

            if not result.data:
                _json_response(self, 401, {"error": "Invalid credentials"})
                return

            user = result.data[0]
            if _hash_password(password, user["salt"]) != user["password_hash"]:
                _json_response(self, 401, {"error": "Invalid credentials"})
                return

            # Update last_login
            now = datetime.now(timezone.utc).isoformat()
            supabase.table("users").update({"last_login": now}).eq("id", user["id"]).execute()

            # Create auth token
            token = secrets.token_urlsafe(48)
            expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
            supabase.table("auth_tokens").insert({
                "token": token,
                "user_id": user["id"],
                "created_at": now,
                "expires_at": expires,
            }).execute()

            _json_response(self, 200, {
                "token": token,
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "username": user["username"],
                    "role": user["role"],
                    "display_name": user["display_name"],
                    "subscription_tier": user.get("subscription_tier", "free"),
                }
            })
        except RuntimeError:
            _json_response(self, 503, {"error": "Supabase not configured"})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def _handle_register(self, body):
        email = body.get("email")
        username = body.get("username")
        password = body.get("password")
        role = body.get("role", "student")
        display_name = body.get("display_name")

        if not email or not username or not password:
            _json_response(self, 400, {"error": "email, username, and password are required"})
            return

        try:
            from lib.supabase_client import get_supabase
            supabase = get_supabase()

            salt = secrets.token_hex(16)
            pw_hash = _hash_password(password, salt)
            now = datetime.now(timezone.utc).isoformat()

            result = supabase.table("users").insert({
                "email": email,
                "username": username,
                "password_hash": pw_hash,
                "salt": salt,
                "role": role,
                "display_name": display_name or username,
                "created_at": now,
            }).execute()

            user = result.data[0] if result.data else {}

            # Auto-login: create token
            token = secrets.token_urlsafe(48)
            expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
            supabase.table("auth_tokens").insert({
                "token": token,
                "user_id": user["id"],
                "created_at": now,
                "expires_at": expires,
            }).execute()

            _json_response(self, 201, {
                "token": token,
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "username": user["username"],
                    "role": user["role"],
                    "display_name": user.get("display_name", username),
                }
            })
        except RuntimeError:
            _json_response(self, 503, {"error": "Supabase not configured"})
        except Exception as e:
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                _json_response(self, 409, {"error": "Email or username already exists"})
            else:
                _json_response(self, 500, {"error": str(e)})

    def _handle_validate(self, body):
        token = body.get("token")
        if not token:
            _json_response(self, 400, {"error": "token is required"})
            return

        try:
            from lib.supabase_client import get_supabase
            supabase = get_supabase()

            result = supabase.table("auth_tokens").select(
                "*, users!auth_tokens_user_id_fkey(id, email, username, role, display_name, subscription_tier)"
            ).eq("token", token).execute()

            if not result.data:
                _json_response(self, 401, {"error": "Invalid token"})
                return

            token_row = result.data[0]
            expires = datetime.fromisoformat(token_row["expires_at"].replace("Z", "+00:00"))
            if expires < datetime.now(timezone.utc):
                # Clean up expired token
                supabase.table("auth_tokens").delete().eq("token", token).execute()
                _json_response(self, 401, {"error": "Token expired"})
                return

            _json_response(self, 200, {
                "valid": True,
                "user": token_row["users"],
            })
        except RuntimeError:
            _json_response(self, 503, {"error": "Supabase not configured"})
        except Exception as e:
            _json_response(self, 500, {"error": str(e)})

    def do_OPTIONS(self):
        self.send_response(204)
        _cors_headers(self)
        self.end_headers()
