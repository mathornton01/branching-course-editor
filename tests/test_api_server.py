#!/usr/bin/env python3
"""
Unit tests for the Branching Courses FastAPI API server.

Run with:  python3 -m pytest tests/test_api_server.py -v
"""
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Make the source module importable
# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import course_api_server  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    """Redirect all file I/O to an isolated temp directory for each test."""
    courses_dir = tmp_path / "courses"
    courses_dir.mkdir()
    catalog_path = courses_dir / "catalog.json"
    catalog_path.write_text(json.dumps({"courses": [], "generated": 0, "last_updated": None}))
    media_dir = courses_dir / "media"
    media_dir.mkdir()

    monkeypatch.setattr(course_api_server, "COURSES_DIR", courses_dir)
    monkeypatch.setattr(course_api_server, "CATALOG_PATH", catalog_path)
    monkeypatch.setattr(course_api_server, "MEDIA_DIR", media_dir)

    return courses_dir


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    return TestClient(course_api_server.app)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_COURSE = {
    "id": "test-course-1",
    "course": {
        "id": "test-course-1",
        "title": "Unit Test Course",
        "description": "A course created by the test suite.",
        "topic": "testing",
        "difficulty": "beginner",
        "tags": ["test", "unit"],
    },
    "nodes": [
        {"id": "n1", "type": "content", "title": "Intro", "content": "Welcome!",
         "position": {"x": 100, "y": 100}},
        {"id": "n2", "type": "decision", "title": "Choose", "content": "",
         "position": {"x": 300, "y": 100},
         "options": [{"id": "opt-a", "label": "A"}, {"id": "opt-b", "label": "B"}]},
        {"id": "n3", "type": "end", "title": "Done", "content": "",
         "position": {"x": 500, "y": 100}},
    ],
    "connections": [
        {"from": "n1", "to": "n2", "type": "default"},
        {"from": "n2", "to": "n3", "type": "default", "label": "Option A"},
    ],
}

SAMPLE_COURSE_2 = {
    "id": "test-course-2",
    "course": {
        "id": "test-course-2",
        "title": "Advanced Testing",
        "description": "Second test course for filtering.",
        "topic": "advanced",
        "difficulty": "intermediate",
        "tags": ["test", "advanced"],
    },
    "nodes": [
        {"id": "x1", "type": "content", "title": "Start", "content": "Go",
         "position": {"x": 0, "y": 0}},
    ],
    "connections": [],
}


def _put(client, course_id, body):
    return client.put(f"/api/courses/{course_id}", json=body)


# ===========================================================================
# GET /api/courses  --  list, filter, search
# ===========================================================================

class TestListCourses:

    def test_empty_catalog(self, client):
        r = client.get("/api/courses")
        assert r.status_code == 200
        assert r.json()["courses"] == []
        assert r.json()["total"] == 0

    def test_list_after_save(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        r = client.get("/api/courses")
        assert r.status_code == 200
        assert r.json()["total"] == 1
        assert r.json()["courses"][0]["id"] == "test-course-1"

    def test_filter_by_tag(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        _put(client, "test-course-2", SAMPLE_COURSE_2)
        r = client.get("/api/courses", params={"tag": "advanced"})
        courses = r.json()["courses"]
        assert len(courses) == 1
        assert courses[0]["id"] == "test-course-2"

    def test_filter_by_tag_case_insensitive(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        r = client.get("/api/courses", params={"tag": "UNIT"})
        assert len(r.json()["courses"]) == 1

    def test_filter_by_difficulty(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        _put(client, "test-course-2", SAMPLE_COURSE_2)
        r = client.get("/api/courses", params={"difficulty": "intermediate"})
        courses = r.json()["courses"]
        assert len(courses) == 1
        assert courses[0]["id"] == "test-course-2"

    def test_filter_by_difficulty_case_insensitive(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        r = client.get("/api/courses", params={"difficulty": "BEGINNER"})
        assert len(r.json()["courses"]) == 1

    def test_search_by_title(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        _put(client, "test-course-2", SAMPLE_COURSE_2)
        r = client.get("/api/courses", params={"search": "Advanced"})
        courses = r.json()["courses"]
        assert len(courses) == 1
        assert courses[0]["id"] == "test-course-2"

    def test_search_by_description(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        r = client.get("/api/courses", params={"search": "test suite"})
        assert len(r.json()["courses"]) == 1

    def test_search_by_topic(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        r = client.get("/api/courses", params={"search": "testing"})
        assert len(r.json()["courses"]) == 1

    def test_search_no_results(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        r = client.get("/api/courses", params={"search": "xyznonexistent"})
        assert r.json()["courses"] == []

    def test_combined_tag_and_difficulty(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        _put(client, "test-course-2", SAMPLE_COURSE_2)
        r = client.get("/api/courses", params={"tag": "test", "difficulty": "beginner"})
        courses = r.json()["courses"]
        assert len(courses) == 1
        assert courses[0]["id"] == "test-course-1"

    def test_list_multiple_courses(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        _put(client, "test-course-2", SAMPLE_COURSE_2)
        r = client.get("/api/courses")
        assert r.json()["total"] == 2


# ===========================================================================
# GET /api/courses/{id}  --  load specific course
# ===========================================================================

class TestGetCourse:

    def test_get_existing(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        r = client.get("/api/courses/test-course-1")
        assert r.status_code == 200
        data = r.json()
        assert data["course"]["title"] == "Unit Test Course"
        assert len(data["nodes"]) == 3

    def test_get_nonexistent_returns_404(self, client):
        r = client.get("/api/courses/nonexistent")
        assert r.status_code == 404

    def test_404_detail_message(self, client):
        r = client.get("/api/courses/no-such-id")
        assert "not found" in r.json()["detail"].lower()

    def test_get_play_alias(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        r = client.get("/api/courses/test-course-1/play")
        assert r.status_code == 200
        assert r.json()["course"]["title"] == "Unit Test Course"


# ===========================================================================
# POST /api/courses  --  create new course
# ===========================================================================

class TestCreateCourse:

    def test_create_with_explicit_id(self, client):
        body = {**SAMPLE_COURSE, "id": "new-course"}
        r = client.post("/api/courses", json=body)
        assert r.status_code == 200
        assert r.json()["id"] == "new-course"
        # Verify persisted
        r2 = client.get("/api/courses/new-course")
        assert r2.status_code == 200

    def test_create_auto_generates_id(self, client):
        body = {
            "course": {"title": "Auto ID", "description": "no id provided"},
            "nodes": [], "connections": []
        }
        r = client.post("/api/courses", json=body)
        assert r.status_code == 200
        cid = r.json()["id"]
        assert cid.startswith("course-")

    def test_create_invalid_id_rejected(self, client):
        body = {**SAMPLE_COURSE, "id": "../../../etc/passwd"}
        r = client.post("/api/courses", json=body)
        assert r.status_code == 400

    def test_create_updates_catalog(self, client):
        _put(client, "c1", SAMPLE_COURSE)
        r = client.get("/api/courses")
        assert r.json()["total"] == 1

    def test_create_empty_body(self, client):
        r = client.post("/api/courses", json={})
        assert r.status_code == 200


# ===========================================================================
# PUT /api/courses/{id}  --  update course
# ===========================================================================

class TestUpdateCourse:

    def test_update_existing(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        updated = {**SAMPLE_COURSE}
        updated["course"] = {**updated["course"], "title": "Updated Title"}
        r = _put(client, "test-course-1", updated)
        assert r.status_code == 200
        r2 = client.get("/api/courses/test-course-1")
        assert r2.json()["course"]["title"] == "Updated Title"

    def test_update_creates_if_new(self, client):
        r = _put(client, "brand-new", SAMPLE_COURSE)
        assert r.status_code == 200
        r2 = client.get("/api/courses/brand-new")
        assert r2.status_code == 200

    def test_update_invalid_id_rejected(self, client):
        r = client.put("/api/courses/bad id!!", json=SAMPLE_COURSE)
        assert r.status_code == 400

    def test_update_catalog_entry_replaced(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        updated = {**SAMPLE_COURSE}
        updated["course"] = {**updated["course"], "title": "V2"}
        _put(client, "test-course-1", updated)
        r = client.get("/api/courses")
        courses = r.json()["courses"]
        assert len(courses) == 1
        assert courses[0]["title"] == "V2"

    def test_put_returns_ok_and_id(self, client):
        r = _put(client, "test-abc", SAMPLE_COURSE)
        data = r.json()
        assert data["ok"] is True
        assert data["id"] == "test-abc"


# ===========================================================================
# DELETE /api/courses/{id}  --  not implemented
# ===========================================================================

class TestDeleteCourse:

    def test_delete_not_implemented(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        r = client.delete("/api/courses/test-course-1")
        assert r.status_code == 405


# ===========================================================================
# GET /api/catalog
# ===========================================================================

class TestCatalog:

    def test_get_catalog_empty(self, client):
        r = client.get("/api/catalog")
        assert r.status_code == 200
        assert r.json()["courses"] == []

    def test_get_catalog_after_saves(self, client):
        _put(client, "c1", SAMPLE_COURSE)
        _put(client, "c2", SAMPLE_COURSE_2)
        r = client.get("/api/catalog")
        data = r.json()
        assert data["generated"] == 2
        assert len(data["courses"]) == 2
        assert data["last_updated"] is not None

    def test_catalog_sync_after_update(self, client):
        _put(client, "c1", SAMPLE_COURSE)
        updated = {**SAMPLE_COURSE}
        updated["course"] = {**updated["course"], "title": "Changed"}
        _put(client, "c1", updated)
        r = client.get("/api/catalog")
        courses = r.json()["courses"]
        assert len(courses) == 1
        assert courses[0]["title"] == "Changed"


# ===========================================================================
# GET /api/random
# ===========================================================================

class TestRandomCourse:

    def test_random_404_when_empty(self, client):
        r = client.get("/api/random")
        assert r.status_code == 404

    def test_random_returns_course(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        r = client.get("/api/random")
        assert r.status_code == 200
        data = r.json()
        assert "course" in data or "nodes" in data


# ===========================================================================
# Media endpoints
# ===========================================================================

class TestMediaEndpoints:

    def test_list_media_empty(self, client):
        r = client.get("/api/courses/test-course-1/media")
        assert r.status_code == 200
        assert r.json()["files"] == []

    def test_upload_media(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        content = b"fake image data"
        r = client.post(
            "/api/courses/test-course-1/media",
            files=[("files", ("test.png", content, "image/png"))],
        )
        assert r.status_code == 200
        uploaded = r.json()["uploaded"]
        assert len(uploaded) == 1
        assert uploaded[0]["filename"] == "test.png"
        assert uploaded[0]["size"] == len(content)

    def test_upload_multiple_files(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        r = client.post(
            "/api/courses/test-course-1/media",
            files=[
                ("files", ("a.png", b"aaa", "image/png")),
                ("files", ("b.jpg", b"bbb", "image/jpeg")),
            ],
        )
        assert r.status_code == 200
        assert len(r.json()["uploaded"]) == 2

    def test_upload_unsupported_type_rejected(self, client):
        r = client.post(
            "/api/courses/test-course-1/media",
            files=[("files", ("evil.exe", b"MZ", "application/x-msdownload"))],
        )
        assert r.status_code == 415

    def test_upload_invalid_course_id(self, client):
        r = client.post(
            "/api/courses/bad!!id/media",
            files=[("files", ("ok.png", b"data", "image/png"))],
        )
        assert r.status_code == 400

    def test_list_media_after_upload(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        client.post(
            "/api/courses/test-course-1/media",
            files=[("files", ("pic.png", b"pixels", "image/png"))],
        )
        r = client.get("/api/courses/test-course-1/media")
        files = r.json()["files"]
        assert len(files) == 1
        assert files[0]["filename"] == "pic.png"

    def test_delete_media(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        client.post(
            "/api/courses/test-course-1/media",
            files=[("files", ("del.png", b"data", "image/png"))],
        )
        r = client.delete("/api/courses/test-course-1/media/del.png")
        assert r.status_code == 200
        assert r.json()["deleted"] == "del.png"
        # Verify gone
        r2 = client.get("/api/courses/test-course-1/media")
        assert r2.json()["files"] == []

    def test_delete_media_not_found(self, client):
        r = client.delete("/api/courses/test-course-1/media/nofile.png")
        assert r.status_code == 404

    def test_delete_media_invalid_course_id(self, client):
        r = client.delete("/api/courses/bad!!id/media/file.png")
        assert r.status_code == 400

    def test_delete_media_invalid_filename(self, client):
        r = client.delete("/api/courses/test-course-1/media/bad%20file!.png")
        assert r.status_code == 400

    def test_upload_filename_collision_renamed(self, client):
        _put(client, "test-course-1", SAMPLE_COURSE)
        client.post(
            "/api/courses/test-course-1/media",
            files=[("files", ("dup.png", b"first", "image/png"))],
        )
        r = client.post(
            "/api/courses/test-course-1/media",
            files=[("files", ("dup.png", b"second", "image/png"))],
        )
        assert r.status_code == 200
        name2 = r.json()["uploaded"][0]["filename"]
        assert name2 != "dup.png"
        assert "dup" in name2

    def test_upload_sanitizes_filename(self, client):
        import re
        _put(client, "test-course-1", SAMPLE_COURSE)
        r = client.post(
            "/api/courses/test-course-1/media",
            files=[("files", ("bad file name!@#.png", b"data", "image/png"))],
        )
        assert r.status_code == 200
        fname = r.json()["uploaded"][0]["filename"]
        assert re.match(r'^[a-zA-Z0-9_\-\.]+$', fname)


# ===========================================================================
# Error cases
# ===========================================================================

class TestErrorCases:

    def test_invalid_course_id_chars_put(self, client):
        r = client.put("/api/courses/has spaces", json=SAMPLE_COURSE)
        assert r.status_code == 400

    def test_get_course_nonexistent(self, client):
        r = client.get("/api/courses/does-not-exist")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()

    def test_missing_catalog_file(self, client, isolated_dirs):
        cat = isolated_dirs / "catalog.json"
        if cat.exists():
            cat.unlink()
        r = client.get("/api/courses")
        assert r.status_code == 200
        assert r.json()["courses"] == []

    def test_catalog_generated_count_accurate(self, client):
        _put(client, "a", SAMPLE_COURSE)
        _put(client, "b", SAMPLE_COURSE_2)
        r = client.get("/api/catalog")
        assert r.json()["generated"] == 2

    def test_catalog_last_updated_set(self, client):
        _put(client, "a", SAMPLE_COURSE)
        r = client.get("/api/catalog")
        assert r.json()["last_updated"] is not None
        assert "T" in r.json()["last_updated"]  # ISO format


# ===========================================================================
# Catalog sync after CRUD operations
# ===========================================================================

class TestCatalogSync:

    def test_create_adds_to_catalog(self, client, isolated_dirs):
        _put(client, "s1", SAMPLE_COURSE)
        catalog = json.loads((isolated_dirs / "catalog.json").read_text())
        assert len(catalog["courses"]) == 1
        assert catalog["courses"][0]["id"] == "s1"

    def test_update_replaces_catalog_entry(self, client, isolated_dirs):
        _put(client, "s1", SAMPLE_COURSE)
        updated = {**SAMPLE_COURSE}
        updated["course"] = {**updated["course"], "title": "V2", "tags": ["updated"]}
        _put(client, "s1", updated)
        catalog = json.loads((isolated_dirs / "catalog.json").read_text())
        assert len(catalog["courses"]) == 1
        assert catalog["courses"][0]["title"] == "V2"
        assert catalog["courses"][0]["tags"] == ["updated"]

    def test_catalog_preserves_order(self, client, isolated_dirs):
        _put(client, "first", SAMPLE_COURSE)
        _put(client, "second", SAMPLE_COURSE_2)
        catalog = json.loads((isolated_dirs / "catalog.json").read_text())
        assert catalog["courses"][0]["id"] == "first"
        assert catalog["courses"][1]["id"] == "second"

    def test_catalog_metadata_extraction(self, client, isolated_dirs):
        _put(client, "meta-test", SAMPLE_COURSE)
        catalog = json.loads((isolated_dirs / "catalog.json").read_text())
        entry = catalog["courses"][0]
        assert entry["title"] == "Unit Test Course"
        assert entry["description"] == "A course created by the test suite."
        assert entry["topic"] == "testing"
        assert entry["difficulty"] == "beginner"
        assert entry["tags"] == ["test", "unit"]

    def test_multiple_creates_increment_generated(self, client, isolated_dirs):
        _put(client, "a", SAMPLE_COURSE)
        _put(client, "b", SAMPLE_COURSE_2)
        catalog = json.loads((isolated_dirs / "catalog.json").read_text())
        assert catalog["generated"] == 2
