#!/usr/bin/env python3
"""
Course improver — uses claude-haiku-4-5 to continuously scan existing courses,
identify weak spots, and add/enrich nodes (examples, practice paths, richer content).
Runs as a background daemon alongside the generator.
"""
import json
import random
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import subprocess

COURSES_DIR = Path(__file__).parent / "courses"
CATALOG_PATH = COURSES_DIR / "catalog.json"
JOURNAL_PATH = Path(__file__).parent / "journal.log"
IMPROVER_LOG = Path(__file__).parent / "improver.log"

MODEL = "claude-haiku-4-5-20251001"
CLAUDE_BIN = "/home/mathornton/.local/bin/claude"

# How long to wait between improvement cycles (seconds)
CYCLE_INTERVAL = 120  # 2 minutes
# Don't improve the same course more than once per session unless it's been a while
COOLDOWN_SECONDS = 600  # 10 minutes per course

IMPROVE_PROMPT = """You are an expert instructional designer improving an existing adaptive branching course.

You will receive a course JSON. Your job is to improve it by:
1. Adding worked EXAMPLE nodes before assessments that lack them (show step-by-step solutions)
2. Adding PRACTICE (remedial) nodes where assessments have failure paths but no practice node
3. Enriching thin content nodes (fewer than 3 sentences) with more explanation
4. Adding richer per-option feedback and explanations to assessment questions that lack them
5. Ensuring every assessment has a failure_target pointing to a practice node (not directly to another content node)
6. Adding a DECISION node somewhere meaningful to let the learner choose a path or depth

Rules:
- Preserve ALL existing node ids and connections — do not remove or rename anything
- Only ADD new nodes and connections, or ENRICH existing text fields
- New node ids must be new UUIDs (use format "node-<uuid4-short>")
- New connections must follow format: {id, source, target, label}
- The course must remain valid — no dangling next/success_target/failure_target references
- Output ONLY valid JSON of the COMPLETE improved course (same schema as input)
- No commentary, no markdown fences, just raw JSON

=== INPUT COURSE ===
{course_json}
"""

def log(msg: str, path: Path = IMPROVER_LOG):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(path, "a") as f:
        f.write(line + "\n")

def log_journal(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(JOURNAL_PATH, "a") as f:
        f.write(f"[{ts}] [IMPROVER] {msg}\n")

def get_course_files():
    return [f for f in COURSES_DIR.glob("*.json") if f.name != "catalog.json"]

def needs_improvement(course: dict) -> tuple[bool, str]:
    """Return (needs_work, reason) — quick heuristics before spending API calls."""
    nodes = course.get("nodes", [])
    types = {n["type"] for n in nodes}
    node_map = {n["id"]: n for n in nodes}

    # Fewer than 10 nodes — definitely sparse
    if len(nodes) < 10:
        return True, f"only {len(nodes)} nodes — too sparse"

    # Any assessment with no preceding example
    for i, node in enumerate(nodes):
        if node["type"] == "assessment":
            # check if any node with next pointing here is an example
            predecessors = [n for n in nodes if n.get("next") == node["id"] or
                            n.get("success_target") == node["id"] or
                            n.get("failure_target") == node["id"]]
            pred_types = {p["type"] for p in predecessors}
            if "example" not in pred_types:
                return True, f"assessment '{node.get('title','?')}' has no example node leading to it"

    # Any assessment failure_target points to a content node (not practice)
    for node in nodes:
        if node["type"] == "assessment":
            ft = node.get("failure_target")
            if ft and ft in node_map and node_map[ft]["type"] == "content":
                return True, f"assessment '{node.get('title','?')}' failure goes to content, not practice"

    # No practice nodes at all
    if "practice" not in types:
        return True, "no practice (remedial) nodes present"

    # No example nodes at all
    if "example" not in types:
        return True, "no example nodes present"

    # No decision nodes
    if "decision" not in types:
        return True, "no decision nodes — adding learner agency"

    return False, ""

def strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

def fix_escapes(text: str) -> str:
    # Fix common JSON issues from LLM output
    text = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', text)
    return text

def call_claude(prompt: str) -> str:
    result = subprocess.run(
        [CLAUDE_BIN, "--print", "--output-format", "text",
         "--model", MODEL, "--no-session-persistence"],
        input=prompt,
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude error: {result.stderr[:300]}")
    return result.stdout.strip()

def improve_course(course_file: Path) -> bool:
    """Load a course, ask Haiku to improve it, save back. Returns True on success."""
    try:
        original_text = course_file.read_text()
        course = json.loads(original_text)
    except Exception as e:
        log(f"SKIP {course_file.name} — parse error: {e}")
        return False

    needs, reason = needs_improvement(course)
    if not needs:
        log(f"SKIP {course_file.name} — already rich enough")
        return False

    title = course.get("title", course_file.name)
    log(f"IMPROVING '{title}' — reason: {reason}")
    log_journal(f"Improving course '{title}' — {reason}")

    course_json = json.dumps(course, indent=2)
    prompt = IMPROVE_PROMPT.replace("{course_json}", course_json)

    try:
        raw = call_claude(prompt)
    except Exception as e:
        log(f"ERROR calling Claude for '{title}': {e}")
        return False

    raw = strip_fences(raw)
    raw = fix_escapes(raw)

    try:
        improved = json.loads(raw)
    except json.JSONDecodeError as e:
        log(f"ERROR parsing improved JSON for '{title}': {e} — skipping")
        return False

    # Sanity checks
    if "nodes" not in improved or len(improved["nodes"]) < len(course["nodes"]):
        log(f"ERROR: improved course has fewer nodes than original — skipping")
        return False

    # Preserve original id and metadata
    improved["id"] = course["id"]
    improved["improved_at"] = datetime.now(timezone.utc).isoformat()
    improved["improved_by"] = MODEL
    old_count = len(course["nodes"])
    new_count = len(improved["nodes"])

    course_file.write_text(json.dumps(improved, indent=2))
    log(f"SAVED '{title}' — {old_count} → {new_count} nodes (+{new_count - old_count})")
    log_journal(f"Improved '{title}': {old_count} → {new_count} nodes")

    # Update catalog entry if present
    try:
        catalog = json.loads(CATALOG_PATH.read_text())
        for entry in catalog.get("courses", []):
            if entry["id"] == improved["id"]:
                entry["node_count"] = new_count
                entry["connection_count"] = len(improved.get("connections", []))
                entry["improved_at"] = improved["improved_at"]
                break
        CATALOG_PATH.write_text(json.dumps(catalog, indent=2))
    except Exception as e:
        log(f"WARN: could not update catalog: {e}")

    return True

def main():
    log("Course improver started")
    log_journal("Course improver daemon started")
    improved_at: dict[str, float] = {}  # course_id -> timestamp

    while True:
        files = get_course_files()
        random.shuffle(files)

        improved_any = False
        for cf in files:
            try:
                course_id = cf.stem
                last = improved_at.get(course_id, 0)
                if time.time() - last < COOLDOWN_SECONDS:
                    continue

                ok = improve_course(cf)
                if ok:
                    improved_at[course_id] = time.time()
                    improved_any = True
                    break  # one improvement per cycle, then wait
            except Exception as e:
                log(f"UNEXPECTED ERROR on {cf.name}: {e}")

        if not improved_any:
            log("No courses needed improvement this cycle — sleeping")

        time.sleep(CYCLE_INTERVAL)

if __name__ == "__main__":
    main()
