#!/usr/bin/env python3
"""
FastAPI server for branching courses project.
Serves static files + REST API for course catalog, store, auth, and analytics.
"""
import json
import shutil
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import re
import threading
import time as _time
import store_db as db

SRC_DIR = Path(__file__).parent
COURSES_DIR = SRC_DIR / "courses"
CATALOG_PATH = COURSES_DIR / "catalog.json"
MEDIA_DIR = COURSES_DIR / "media"

ALLOWED_MEDIA_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml',
    'video/mp4', 'video/webm', 'audio/mpeg', 'audio/ogg', 'audio/wav',
    'application/pdf', 'text/plain',
}
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

app = FastAPI(title="Branching Courses API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Auto-rebuild catalog on startup and periodically ---

def _rebuild_catalog():
    """Scan all course JSON files and rebuild catalog.json."""
    from datetime import datetime, timezone
    courses = []
    for f in sorted(COURSES_DIR.glob("*.json")):
        if f.name == "catalog.json":
            continue
        try:
            data = json.loads(f.read_text())
        except Exception:
            continue
        course_id = data.get("id") or f.stem
        courses.append({
            "id": course_id,
            "title": data.get("title", f.stem),
            "description": data.get("description", ""),
            "topic": data.get("topic", ""),
            "theme": data.get("theme"),
            "difficulty": data.get("difficulty", "beginner"),
            "estimated_minutes": data.get("estimated_minutes", 15),
            "tags": data.get("tags", []),
            "generated_at": data.get("generated_at"),
            "node_count": len(data.get("nodes", [])),
            "connection_count": len(data.get("connections", [])),
            "filename": f.name,
        })
    catalog = {
        "courses": courses,
        "generated": len(courses),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2))
    return len(courses)

def _periodic_rebuild(interval=120):
    """Background thread: rebuild catalog every `interval` seconds."""
    while True:
        _time.sleep(interval)
        try:
            _rebuild_catalog()
        except Exception:
            pass

# Rebuild on startup
_rebuild_catalog()
# Start background rebuilder (every 2 minutes)
_rebuild_thread = threading.Thread(target=_periodic_rebuild, args=(120,), daemon=True)
_rebuild_thread.start()

@app.get("/api/rebuild-catalog")
def rebuild_catalog_endpoint():
    """Force rebuild the catalog from all course files."""
    count = _rebuild_catalog()
    return {"ok": True, "courses_indexed": count}

# --- API routes (must be before static mount) ---

@app.get("/api/courses")
def list_courses(tag: str = None, difficulty: str = None, search: str = None):
    """List all courses in the catalog with optional filters."""
    if not CATALOG_PATH.exists():
        return {"courses": [], "generated": 0, "last_updated": None}
    catalog = json.loads(CATALOG_PATH.read_text())
    courses = catalog.get("courses", [])

    if tag:
        courses = [c for c in courses if tag.lower() in [t.lower() for t in c.get("tags", [])]]
    if difficulty:
        courses = [c for c in courses if c.get("difficulty", "").lower() == difficulty.lower()]
    if search:
        q = search.lower()
        courses = [c for c in courses if q in c.get("title", "").lower() or q in c.get("description", "").lower() or q in c.get("topic", "").lower()]

    return {
        "courses": courses,
        "total": len(courses),
        "generated": catalog.get("generated", len(courses)),
        "last_updated": catalog.get("last_updated"),
    }

@app.get("/api/courses/{course_id}")
def get_course(course_id: str):
    """Get full course data by ID."""
    course_path = COURSES_DIR / f"{course_id}.json"
    if not course_path.exists():
        raise HTTPException(status_code=404, detail="Course not found")
    return json.loads(course_path.read_text())

@app.get("/api/courses/{course_id}/play")
def get_course_for_player(course_id: str):
    """Get course data formatted for the player (alias of get_course)."""
    return get_course(course_id)

@app.get("/api/catalog")
def get_catalog():
    """Get the full catalog metadata."""
    if not CATALOG_PATH.exists():
        return {"courses": [], "generated": 0}
    return json.loads(CATALOG_PATH.read_text())

@app.get("/api/random")
def get_random_course():
    """Get a random course."""
    import random
    if not CATALOG_PATH.exists():
        raise HTTPException(status_code=404, detail="No courses yet")
    catalog = json.loads(CATALOG_PATH.read_text())
    courses = catalog.get("courses", [])
    if not courses:
        raise HTTPException(status_code=404, detail="No courses yet")
    course_meta = random.choice(courses)
    return get_course(course_meta["id"])

@app.put("/api/courses/{course_id}")
def save_course(course_id: str, body: Dict[str, Any]):
    """Save (create or update) a course by ID. Accepts both flat and branching formats."""
    # Sanitize course_id
    if not re.match(r'^[a-zA-Z0-9_\-]+$', course_id):
        raise HTTPException(status_code=400, detail="Invalid course ID")

    course_path = COURSES_DIR / f"{course_id}.json"
    COURSES_DIR.mkdir(parents=True, exist_ok=True)

    # Write course file
    course_path.write_text(json.dumps(body, indent=2))

    # Update catalog
    _update_catalog(course_id, body)

    return {"ok": True, "id": course_id}


@app.post("/api/courses")
def create_course(body: Dict[str, Any]):
    """Create a new course. Auto-generates ID if not provided."""
    import time
    course_id = body.get("id") or body.get("course", {}).get("id")
    if not course_id:
        course_id = f"course-{int(time.time())}"
    if not re.match(r'^[a-zA-Z0-9_\-]+$', course_id):
        raise HTTPException(status_code=400, detail="Invalid course ID")
    body["id"] = course_id
    return save_course(course_id, body)


@app.get("/api/courses/{course_id}/media")
def list_course_media(course_id: str):
    """List all media files attached to a course."""
    if not re.match(r'^[a-zA-Z0-9_\-]+$', course_id):
        raise HTTPException(status_code=400, detail="Invalid course ID")
    media_path = MEDIA_DIR / course_id
    if not media_path.exists():
        return {"files": []}
    files = []
    for f in sorted(media_path.iterdir()):
        if f.is_file():
            files.append({
                "filename": f.name,
                "size": f.stat().st_size,
                "url": f"/courses/media/{course_id}/{f.name}",
            })
    return {"files": files}


@app.post("/api/courses/{course_id}/media")
async def upload_course_media(course_id: str, files: List[UploadFile] = File(...)):
    """Upload one or more media files for a course."""
    if not re.match(r'^[a-zA-Z0-9_\-]+$', course_id):
        raise HTTPException(status_code=400, detail="Invalid course ID")
    media_path = MEDIA_DIR / course_id
    media_path.mkdir(parents=True, exist_ok=True)
    saved = []
    for upload in files:
        if upload.content_type and upload.content_type not in ALLOWED_MEDIA_TYPES:
            raise HTTPException(status_code=415, detail=f"Unsupported media type: {upload.content_type}")
        # Sanitize filename
        safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', upload.filename or 'file')
        dest = media_path / safe_name
        # Avoid collisions
        if dest.exists():
            stem = dest.stem
            suffix = dest.suffix
            i = 1
            while dest.exists():
                dest = media_path / f"{stem}_{i}{suffix}"
                i += 1
        content = await upload.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=413, detail="File too large (max 50 MB)")
        dest.write_bytes(content)
        saved.append({
            "filename": dest.name,
            "size": len(content),
            "url": f"/courses/media/{course_id}/{dest.name}",
            "content_type": upload.content_type,
        })
    return {"uploaded": saved}


@app.delete("/api/courses/{course_id}/media/{filename}")
def delete_course_media(course_id: str, filename: str):
    """Delete a media file from a course."""
    if not re.match(r'^[a-zA-Z0-9_\-]+$', course_id):
        raise HTTPException(status_code=400, detail="Invalid course ID")
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    dest = MEDIA_DIR / course_id / filename
    if not dest.exists():
        raise HTTPException(status_code=404, detail="File not found")
    dest.unlink()
    return {"ok": True, "deleted": filename}


def _update_catalog(course_id: str, body: Dict[str, Any]):
    """Update catalog.json with course metadata."""
    import datetime
    catalog = {"courses": [], "generated": 0, "last_updated": None}
    if CATALOG_PATH.exists():
        try:
            catalog = json.loads(CATALOG_PATH.read_text())
        except Exception:
            pass

    # Extract metadata from either flat or branching format
    course_meta = body.get("course", body)
    title = course_meta.get("title", course_id)
    description = course_meta.get("description", "")
    topic = course_meta.get("topic", "")
    difficulty = course_meta.get("difficulty", "beginner")
    tags = course_meta.get("tags", [])

    entry = {
        "id": course_id,
        "title": title,
        "description": description,
        "topic": topic,
        "difficulty": difficulty,
        "tags": tags,
    }

    courses = catalog.get("courses", [])
    existing_idx = next((i for i, c in enumerate(courses) if c["id"] == course_id), None)
    if existing_idx is not None:
        courses[existing_idx] = entry
    else:
        courses.append(entry)

    catalog["courses"] = courses
    catalog["generated"] = len(courses)
    catalog["last_updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2))


# --- Auth helper ---

def _get_user(authorization: str = Header(None)) -> dict | None:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    return db.validate_token(token)

def _require_user(authorization: str = Header(None)) -> dict:
    user = _get_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

# --- Auth API ---

class RegisterBody(BaseModel):
    email: str
    username: str
    password: str
    role: str = "student"
    display_name: str = None

class LoginBody(BaseModel):
    login: str
    password: str

@app.post("/api/auth/register")
def register(body: RegisterBody):
    try:
        # Normalize "professor" to "instructor" for consistent role storage
        role = "instructor" if body.role == "professor" else body.role
        if role not in ("student", "instructor", "admin"):
            role = "student"
        user = db.create_user(body.email, body.username, body.password, role, body.display_name)
        token = db.create_token(user["id"])
        return {"ok": True, "user": user, "token": token}
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409, detail="Email or username already exists")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/auth/login")
def login(body: LoginBody):
    user = db.authenticate(body.login, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = db.create_token(user["id"])
    return {"ok": True, "user": {"id": user["id"], "email": user["email"], "username": user["username"], "role": user["role"], "display_name": user["display_name"], "subscription_tier": user["subscription_tier"]}, "token": token}

@app.get("/api/auth/me")
def get_me(authorization: str = Header(None)):
    user = _require_user(authorization)
    full = db.get_user(user["user_id"])
    if not full:
        raise HTTPException(status_code=404, detail="User not found")
    return full

# --- Store API ---

class PublishBody(BaseModel):
    price_cents: int = 0
    category: str = None
    is_featured: bool = False
    preview_nodes: int = 3

@app.post("/api/store/publish/{course_id}")
def publish_course(course_id: str, body: PublishBody, authorization: str = Header(None)):
    user = _require_user(authorization)
    if user["role"] not in ("instructor", "admin"):
        raise HTTPException(status_code=403, detail="Only instructors can publish courses")
    course_path = COURSES_DIR / f"{course_id}.json"
    if not course_path.exists():
        raise HTTPException(status_code=404, detail="Course not found")
    db.set_course_store_info(course_id, user["user_id"], body.price_cents, body.category, True, body.is_featured, body.preview_nodes)
    return {"ok": True, "course_id": course_id, "price_cents": body.price_cents}

@app.get("/api/store/browse")
def browse_store(category: str = None, search: str = None, sort: str = "popular", page: int = 1, per_page: int = 24):
    result = db.get_store_courses(category, search, sort, page, per_page)
    # Merge catalog metadata into store listings
    catalog = {}
    if CATALOG_PATH.exists():
        cat_data = json.loads(CATALOG_PATH.read_text())
        for c in cat_data.get("courses", []):
            catalog[c["id"]] = c
    for course in result["courses"]:
        meta = catalog.get(course["course_id"], {})
        course["title"] = meta.get("title", course["course_id"])
        course["description"] = meta.get("description", "")
        course["topic"] = meta.get("topic", "")
        course["difficulty"] = meta.get("difficulty", "beginner")
        course["tags"] = meta.get("tags", [])
        course["node_count"] = meta.get("node_count", 0)
        course["theme"] = meta.get("theme")
    return result

@app.get("/api/store/featured")
def get_featured():
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM courses_store WHERE is_featured=1 AND is_published=1 ORDER BY total_purchases DESC LIMIT 12").fetchall()
    featured = [dict(r) for r in rows]
    # Merge catalog data
    catalog = {}
    if CATALOG_PATH.exists():
        cat_data = json.loads(CATALOG_PATH.read_text())
        for c in cat_data.get("courses", []):
            catalog[c["id"]] = c
    for course in featured:
        meta = catalog.get(course["course_id"], {})
        course["title"] = meta.get("title", course["course_id"])
        course["description"] = meta.get("description", "")
        course["difficulty"] = meta.get("difficulty", "beginner")
        course["topic"] = meta.get("topic", "")
        course["tags"] = meta.get("tags", [])
        course["node_count"] = meta.get("node_count", 0)
    return {"featured": featured}

@app.post("/api/store/purchase/{course_id}")
def purchase(course_id: str, authorization: str = Header(None)):
    user = _require_user(authorization)
    if db.has_purchased(user["user_id"], course_id):
        return {"ok": True, "already_owned": True}
    with db.get_db() as conn:
        store_info = conn.execute("SELECT * FROM courses_store WHERE course_id=? AND is_published=1", (course_id,)).fetchone()
    if not store_info:
        raise HTTPException(status_code=404, detail="Course not in store")
    price = store_info["price_cents"]
    if price == 0:
        result = db.purchase_course(user["user_id"], course_id, 0, "free")
    else:
        result = db.purchase_course(user["user_id"], course_id, price, "card")
    return {"ok": True, **result}

@app.get("/api/store/my-purchases")
def my_purchases(authorization: str = Header(None)):
    user = _require_user(authorization)
    return {"purchases": db.get_user_purchases(user["user_id"])}

@app.get("/api/store/check-access/{course_id}")
def check_access(course_id: str, authorization: str = Header(None)):
    user = _get_user(authorization)
    with db.get_db() as conn:
        store_info = conn.execute("SELECT * FROM courses_store WHERE course_id=?", (course_id,)).fetchone()
    if not store_info:
        return {"has_access": True, "reason": "not_in_store"}
    if store_info["price_cents"] == 0:
        return {"has_access": True, "reason": "free"}
    if not user:
        return {"has_access": False, "reason": "login_required", "price_cents": store_info["price_cents"]}
    if user.get("role") in ("instructor", "admin"):
        return {"has_access": True, "reason": "instructor"}
    if db.has_purchased(user["user_id"], course_id):
        return {"has_access": True, "reason": "purchased"}
    return {"has_access": False, "reason": "purchase_required", "price_cents": store_info["price_cents"]}

# --- Reviews ---

class ReviewBody(BaseModel):
    rating: int
    text: str = None

@app.post("/api/store/review/{course_id}")
def review_course(course_id: str, body: ReviewBody, authorization: str = Header(None)):
    user = _require_user(authorization)
    return db.add_review(user["user_id"], course_id, body.rating, body.text)

@app.get("/api/store/reviews/{course_id}")
def get_reviews(course_id: str):
    with db.get_db() as conn:
        rows = conn.execute("""
            SELECT r.*, u.username, u.display_name FROM reviews r
            JOIN users u ON r.user_id=u.id WHERE r.course_id=? ORDER BY r.created_at DESC
        """, (course_id,)).fetchall()
    return {"reviews": [dict(r) for r in rows]}

# --- Progress Tracking API ---

class StartSessionBody(BaseModel):
    course_id: str
    start_node_id: str = None

class ProgressBody(BaseModel):
    session_id: int
    course_id: str
    node_id: str
    node_type: str = None
    event_type: str
    event_data: dict = None
    attributes: dict = None

class CompleteSessionBody(BaseModel):
    session_id: int
    final_attributes: dict = None
    completion_pct: float = 100

@app.post("/api/progress/start")
def start_play_session(body: StartSessionBody, authorization: str = Header(None)):
    user = _get_user(authorization)
    user_id = user["user_id"] if user else 0
    session_id = db.start_session(user_id, body.course_id, body.start_node_id)
    return {"session_id": session_id}

@app.post("/api/progress/event")
def record_event(body: ProgressBody, authorization: str = Header(None)):
    user = _get_user(authorization)
    user_id = user["user_id"] if user else 0
    db.record_progress(body.session_id, user_id, body.course_id, body.node_id, body.node_type, body.event_type, body.event_data, body.attributes)
    return {"ok": True}

@app.post("/api/progress/complete")
def complete_play_session(body: CompleteSessionBody, authorization: str = Header(None)):
    db.complete_session(body.session_id, body.final_attributes, body.completion_pct)
    return {"ok": True}

# --- Analytics API (for instructors) ---

@app.get("/api/analytics/course/{course_id}")
def course_analytics(course_id: str, authorization: str = Header(None)):
    user = _require_user(authorization)
    if user["role"] not in ("instructor", "admin"):
        raise HTTPException(status_code=403, detail="Instructor access required")
    return db.get_course_analytics(course_id)

@app.get("/api/analytics/student/{student_id}")
def student_analytics(student_id: int, authorization: str = Header(None)):
    user = _require_user(authorization)
    if user["role"] not in ("instructor", "admin") and user["user_id"] != student_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return db.get_student_analytics(student_id)

@app.get("/api/analytics/dashboard")
def instructor_dashboard(authorization: str = Header(None)):
    user = _require_user(authorization)
    if user["role"] not in ("instructor", "admin"):
        raise HTTPException(status_code=403, detail="Instructor access required")
    return db.get_instructor_dashboard(user["user_id"])

# --- Enrollment API ---

class EnrollBody(BaseModel):
    instructor_id: int

@app.post("/api/enroll/{course_id}")
def enroll(course_id: str, body: EnrollBody, authorization: str = Header(None)):
    user = _require_user(authorization)
    if user["role"] not in ("student",):
        raise HTTPException(status_code=403, detail="Only students can enroll in courses")
    result = db.enroll_student(user["user_id"], body.instructor_id, course_id)
    return {"ok": True, **result}

@app.delete("/api/enroll/{course_id}")
def unenroll(course_id: str, authorization: str = Header(None)):
    user = _require_user(authorization)
    db.unenroll_student(user["user_id"], course_id)
    return {"ok": True}

@app.get("/api/my-enrollments")
def my_enrollments(authorization: str = Header(None)):
    user = _require_user(authorization)
    return {"enrollments": db.get_student_enrollments(user["user_id"])}

@app.get("/api/instructor/students")
def instructor_students(authorization: str = Header(None)):
    user = _require_user(authorization)
    if user["role"] not in ("instructor", "admin"):
        raise HTTPException(status_code=403, detail="Instructor access required")
    return {"students": db.get_instructor_enrollments(user["user_id"])}

@app.get("/api/courses/{course_id}/enrollment-count")
def enrollment_count(course_id: str):
    return {"course_id": course_id, "enrolled": db.get_course_enrollment_count(course_id)}

# --- Enrollment Codes ---

class GenerateCodeBody(BaseModel):
    course_id: str
    max_uses: int = 100

@app.post("/api/enrollment-codes/generate")
def generate_code(body: GenerateCodeBody, authorization: str = Header(None)):
    user = _require_user(authorization)
    if user["role"] not in ("instructor", "admin"):
        raise HTTPException(status_code=403, detail="Instructor access required")
    result = db.create_enrollment_code(user["user_id"], body.course_id, body.max_uses)
    return {"ok": True, **result}

class RedeemCodeBody(BaseModel):
    code: str

@app.post("/api/enrollment-codes/redeem")
def redeem_code(body: RedeemCodeBody, authorization: str = Header(None)):
    user = _require_user(authorization)
    if user["role"] not in ("student",):
        raise HTTPException(status_code=403, detail="Only students can redeem enrollment codes")
    try:
        result = db.redeem_enrollment_code(body.code, user["user_id"])
        return {"ok": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/enrollment-codes")
def list_codes(authorization: str = Header(None)):
    user = _require_user(authorization)
    if user["role"] not in ("instructor", "admin"):
        raise HTTPException(status_code=403, detail="Instructor access required")
    return {"codes": db.get_instructor_codes(user["user_id"])}

# --- Bulk publish (admin) ---

@app.post("/api/store/bulk-publish")
def bulk_publish(authorization: str = Header(None), price_cents: int = 99, category: str = None):
    user = _require_user(authorization)
    if user["role"] not in ("instructor", "admin"):
        raise HTTPException(status_code=403, detail="Instructor access required")
    catalog = json.loads(CATALOG_PATH.read_text()) if CATALOG_PATH.exists() else {"courses": []}
    count = 0
    for c in catalog.get("courses", []):
        cid = c["id"]
        topic = c.get("topic", category or "general")
        db.set_course_store_info(cid, user["user_id"], price_cents, topic, True, False, 3)
        count += 1
    return {"ok": True, "published": count}

# --- Static files (after API routes) ---
app.mount("/", StaticFiles(directory=str(SRC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn, argparse, sys
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8090)
    args, _ = parser.parse_known_args()
    uvicorn.run(app, host="0.0.0.0", port=args.port)
