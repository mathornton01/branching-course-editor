#!/usr/bin/env python3
"""Rebuild catalog.json from all course JSON files in courses/."""
import json
from datetime import datetime, timezone
from pathlib import Path

COURSES_DIR = Path(__file__).parent / "courses"
CATALOG_PATH = COURSES_DIR / "catalog.json"

def rebuild():
    courses = []
    skipped = 0
    for f in sorted(COURSES_DIR.glob("*.json")):
        if f.name == "catalog.json":
            continue
        try:
            data = json.loads(f.read_text())
        except Exception as e:
            print(f"  SKIP {f.name}: {e}")
            skipped += 1
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
    print(f"Rebuilt catalog: {len(courses)} courses indexed, {skipped} skipped")

if __name__ == "__main__":
    rebuild()
