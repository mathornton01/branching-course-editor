#!/usr/bin/env python3
"""
FastAPI server for branching courses project.
Serves static files + REST API for course catalog.
"""
import json
import shutil
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Any, Dict, List
import re

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


# --- Static files (after API routes) ---
app.mount("/", StaticFiles(directory=str(SRC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn, argparse, sys
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8090)
    args, _ = parser.parse_known_args()
    uvicorn.run(app, host="0.0.0.0", port=args.port)
