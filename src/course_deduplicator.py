#!/usr/bin/env python3
"""
Course deduplicator — finds duplicate/near-duplicate courses and keeps the better one.

Scoring (higher = better):
  +3 per node (content richness)
  +1 per connection
  +2 if has domain theme
  +1 if has tags
  +5 if improved_at is set
  +2 if estimated_minutes > 0
  -10 if any node has empty content
  -5 per error node (no title or type)

Similarity detection:
  - Exact title match (after normalizing case/punctuation)
  - Topic + difficulty match with title Jaccard similarity > 0.5
  - Node content fingerprint overlap > 60%
"""

import json
import re
import math
import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

COURSES_DIR = Path(__file__).parent / "courses"
CATALOG_PATH = COURSES_DIR / "catalog.json"
DEDUP_LOG = Path(__file__).parent / "dedup.log"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(DEDUP_LOG, "a") as f:
        f.write(line + "\n")


def normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def title_tokens(title: str) -> set:
    stopwords = {"a", "an", "the", "for", "in", "of", "to", "and", "or", "with", "on", "is", "are"}
    return {w for w in normalize_title(title).split() if w not in stopwords}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union)


def node_content_fingerprint(course: dict) -> set:
    """Extract a set of 4-grams from all node content for overlap comparison."""
    text = ""
    for node in course.get("nodes", []):
        text += " " + normalize_title(node.get("title", ""))
        content = node.get("content", "")
        if isinstance(content, str):
            text += " " + content.lower()
    words = text.split()
    grams = set()
    for i in range(len(words) - 3):
        grams.add(tuple(words[i:i+4]))
    return grams


def score_course(course: dict) -> float:
    nodes = course.get("nodes", [])
    connections = course.get("connections", [])
    score = 0.0

    # Richness
    score += len(nodes) * 3
    score += len(connections) * 1

    # Extras
    if course.get("theme"):
        score += 2
    if course.get("tags"):
        score += 1
    if course.get("improved_at"):
        score += 5
    if (course.get("estimated_minutes") or 0) > 0:
        score += 2

    # Penalties
    for node in nodes:
        content = node.get("content", "")
        if isinstance(content, str) and len(content.strip()) < 10:
            score -= 10
        if not node.get("title") or not node.get("type"):
            score -= 5

    return score


def are_duplicates(a: dict, b: dict) -> bool:
    title_a = normalize_title(a.get("title", ""))
    title_b = normalize_title(b.get("title", ""))

    # Exact title match
    if title_a == title_b:
        return True

    # Same topic + difficulty + high title Jaccard
    tok_a = title_tokens(a.get("title", ""))
    tok_b = title_tokens(b.get("title", ""))
    j = jaccard(tok_a, tok_b)
    if (a.get("topic", "").lower() == b.get("topic", "").lower()
            and a.get("difficulty") == b.get("difficulty")
            and j > 0.5):
        return True

    # Content fingerprint overlap
    fp_a = node_content_fingerprint(a)
    fp_b = node_content_fingerprint(b)
    if fp_a and fp_b:
        overlap = len(fp_a & fp_b) / min(len(fp_a), len(fp_b))
        if overlap > 0.6:
            return True

    return False


def rebuild_catalog(courses: list[dict]):
    catalog_entries = []
    for c in courses:
        catalog_entries.append({
            "id": c["id"],
            "title": c.get("title", ""),
            "description": c.get("description", ""),
            "topic": c.get("topic", ""),
            "difficulty": c.get("difficulty", ""),
            "tags": c.get("tags", []),
        })
    catalog = {
        "courses": catalog_entries,
        "generated": len(catalog_entries),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2))
    log(f"Catalog rebuilt with {len(catalog_entries)} courses.")


def load_all_courses() -> list[tuple[Path, dict]]:
    results = []
    for path in COURSES_DIR.glob("*.json"):
        if path.name == "catalog.json":
            continue
        try:
            data = json.loads(path.read_text())
            results.append((path, data))
        except Exception as e:
            log(f"  Skipping unreadable {path.name}: {e}")
    return results


def deduplicate(dry_run=False):
    log("=== Deduplication run started ===")
    pairs = load_all_courses()
    log(f"Loaded {len(pairs)} course files.")

    removed = set()  # paths of losers to delete
    kept = {}        # path -> course (winners)

    for path, course in pairs:
        kept[path] = course

    # O(n^2) comparison — fine for <500 courses
    paths = list(kept.keys())
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            pa, pb = paths[i], paths[j]
            if pa in removed or pb in removed:
                continue
            ca, cb = kept[pa], kept[pb]
            if are_duplicates(ca, cb):
                sa = score_course(ca)
                sb = score_course(cb)
                loser_path = pa if sa < sb else pb
                winner_path = pb if sa < sb else pa
                loser_title = kept[loser_path].get("title", loser_path.name)
                winner_title = kept[winner_path].get("title", winner_path.name)
                log(f"  Duplicate: '{loser_title}' (score {min(sa,sb):.0f}) vs '{winner_title}' (score {max(sa,sb):.0f}) — keeping winner")
                removed.add(loser_path)

    log(f"Found {len(removed)} duplicates to remove.")

    if not dry_run:
        for path in removed:
            path.unlink()
            log(f"  Deleted: {path.name}")

        # Rebuild catalog from survivors
        survivors = [(p, c) for p, c in kept.items() if p not in removed]
        rebuild_catalog([c for _, c in survivors])
    else:
        log("Dry run — no files deleted.")

    log(f"Done. {len(pairs) - len(removed)} courses remain.")
    return len(removed)


def watch_loop(interval_minutes: int):
    log(f"Deduplicator watch mode: running every {interval_minutes} minutes.")
    import time
    while True:
        try:
            removed = deduplicate()
            log(f"Watch cycle complete. Removed {removed} duplicates.")
        except Exception as e:
            log(f"Error in watch cycle: {e}")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Course deduplicator")
    parser.add_argument("--dry-run", action="store_true", help="Show duplicates without deleting")
    parser.add_argument("--watch", type=int, metavar="MINUTES", help="Run continuously every N minutes")
    args = parser.parse_args()

    if args.watch:
        watch_loop(args.watch)
    else:
        deduplicate(dry_run=args.dry_run)
