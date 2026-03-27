#!/usr/bin/env python3
"""
Background course generator — uses claude-haiku-4-5 via Claude CLI to continuously generate
branching courses with optional themes and store them in courses/catalog.json.
"""
import json
import random
import re
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

COURSES_DIR = Path(__file__).parent / "courses"
CATALOG_PATH = COURSES_DIR / "catalog.json"
TOPICS_PATH = Path(__file__).parent / "topics.json"
JOURNAL_PATH = Path(__file__).parent / "journal.log"

MODEL = "claude-haiku-4-5-20251001"
CLAUDE_BIN = "/home/mathornton/.local/bin/claude"

SYSTEM_PROMPT = """You are an expert instructional designer. Generate a compact branching course as valid JSON.

=== NODE TYPES ===
content: {id, type, title, content (markdown, 3-5 sentences), next}
example: {id, type, title, content (1 worked example, 3-4 sentences), next}
assessment: {id, type, title, content, questions, pass_threshold, success_target, failure_target}
  questions format: [{question, options:[A,B,C,D], correct_index:0-3, feedback:[A,B,C,D], explanation}]
  Use 2-3 questions per assessment.
practice: same as assessment, different questions
decision: {id, type, title, content, choices:[{label, next}]}
end: {id, type, title, content}

=== CONNECTIONS ===
{id, source, target, label}

=== OUTPUT FORMAT ===
Output ONLY raw valid JSON (no markdown fences):
{"id":"<uuid>","title":"...","description":"...","topic":"...","theme":null,"difficulty":"beginner|intermediate|advanced","estimated_minutes":<n>,"tags":[...],"nodes":[...],"connections":[...]}

=== STRUCTURE TEMPLATES — pick ONE that suits the topic ===

A) SKILL TREE (learner chooses their path upfront, 2 branches merge at end)
   decision(intro) → [branch A: content→example→assessment] AND [branch B: content→example→assessment] → shared end
   Total: ~9 nodes. Labels on decision choices: e.g. "Theory first" / "Hands-on first"

B) MASTERY LADDER (sequential modules, fail loops back for retry)
   content→assessment [fail→practice→back to assessment] [pass→next content→assessment] → end
   Total: ~8 nodes. Loops allowed — n5 can point back to n3.

C) DIAGNOSTIC BRANCH (opening quiz routes learner to appropriate depth)
   assessment(diagnostic) → [if strong: advanced content→example→end] [if weak: basic content→example→practice→end]
   Total: ~8 nodes. Use pass/fail paths for routing, not a decision node.

D) EXPLORE & CONVERGE (multiple topic areas, learner picks 2 of 3 via decisions)
   intro(content) → decision → [topic A: content→example] AND [topic B: content→example] AND [topic C: content→example]
   All topics → shared synthesis content → end
   Total: ~10-12 nodes. Decision has 3 choices; all paths reconverge.

E) SCENARIO TREE (narrative choices lead to different endings)
   content(scene 1) → decision → [path A: content→decision→[good end / bad end]] [path B: content→end]
   Total: ~9 nodes. 2-3 distinct endings reflecting learner choices.

F) ASSESSMENT PYRAMID (escalating challenge, early exit for advanced learners)
   easy_assessment → [pass: harder_assessment → [pass: expert content → end] [fail: practice → end]]
                   → [fail: remedial content → example → basic end]
   Total: ~8 nodes. Rewards mastery with shorter paths.

Rules:
- Pick the template that makes most sense for the topic
- Node IDs: n1, n2... Connection IDs: c1, c2...
- All nodes must be reachable; every non-end node must have at least one outgoing connection
- Real educational content, not placeholders
- If theme given, use it throughout examples and questions
- Vary node counts: anywhere from 8 to 13 nodes is fine"""


def log_journal(entry: str):
    """Append a timestamped entry to journal.log."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(JOURNAL_PATH, "a") as f:
        f.write(f"[{ts}] {entry}\n")


def load_topics() -> dict:
    if TOPICS_PATH.exists():
        return json.loads(TOPICS_PATH.read_text())
    return {"topics": [], "themes": []}


def load_catalog() -> dict:
    if CATALOG_PATH.exists():
        return json.loads(CATALOG_PATH.read_text())
    return {"courses": [], "generated": 0, "last_updated": None}


def save_catalog(catalog: dict):
    catalog["last_updated"] = datetime.now(timezone.utc).isoformat()
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2))


def get_used_combinations(catalog: dict) -> set:
    """Return set of (topic, theme) tuples already generated."""
    used = set()
    for c in catalog.get("courses", []):
        topic = c.get("topic", "")
        theme = c.get("theme") or None
        used.add((topic, theme))
    return used


def claude_chat(system: str, user: str) -> str:
    full_prompt = f"{system}\n\n{user}"
    result = subprocess.run(
        [CLAUDE_BIN, "--print", "--output-format", "text",
         "--model", MODEL, "--no-session-persistence"],
        input=full_prompt,
        capture_output=True, text=True, timeout=480,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr[:200]}")
    return result.stdout.strip()


STRUCTURE_TEMPLATES = ['A', 'B', 'C', 'D', 'E', 'F']
_template_idx = [0]

def generate_course(topic: str, theme: str | None = None) -> dict | None:
    # Rotate through structure templates so output varies
    template = STRUCTURE_TEMPLATES[_template_idx[0] % len(STRUCTURE_TEMPLATES)]
    _template_idx[0] += 1
    template_hint = f"\nUse structure template {template} from the system prompt.\n"

    if theme:
        prompt = f"""Create a complete branching course on: {topic}
{template_hint}
Theme: {theme}
Every example, analogy, scenario, case study, and practice question MUST be set in the context of {theme}.
The content should teach {topic} entirely through the lens of {theme}.

Make it engaging and educational. Include real content, not placeholders.
The course should teach the topic effectively through adaptive branching.

IMPORTANT: Output ONLY valid JSON. No explanation, no markdown fences, just raw JSON."""
    else:
        prompt = f"""Create a complete branching course on: {topic}
{template_hint}
Make it engaging and educational. Include real content, not placeholders.
The course should teach the topic effectively through adaptive branching.

IMPORTANT: Output ONLY valid JSON. No explanation, no markdown fences, just raw JSON."""

    label = f"{topic}" + (f" [{theme}]" if theme else "")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Generating: {label}...", flush=True)
    log_journal(f"GENERATING: {label}")

    text = claude_chat(SYSTEM_PROMPT, prompt)

    # Extract JSON if wrapped in code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    # Find the outermost JSON object
    start = text.find('{')
    if start > 0:
        text = text[start:]
    end = text.rfind('}')
    if end != -1:
        text = text[:end+1]

    # Fix invalid escape sequences
    valid_escapes = set('"\\bfnrtu/')
    def fix_escapes(s):
        result = []
        i = 0
        while i < len(s):
            if s[i] == '\\' and i + 1 < len(s) and s[i+1] not in valid_escapes:
                result.append('\\\\')
                i += 1
            else:
                result.append(s[i])
                i += 1
        return ''.join(result)

    try:
        course = json.loads(text)
    except json.JSONDecodeError:
        text = fix_escapes(text)
        try:
            course = json.loads(text)
        except json.JSONDecodeError:
            # Last resort: truncate at last valid closing brace
            # Walk backward to find a valid JSON object
            for i in range(len(text), 0, -1):
                if text[i-1] == '}':
                    try:
                        course = json.loads(text[:i])
                        break
                    except json.JSONDecodeError:
                        continue
            else:
                raise json.JSONDecodeError("Could not repair JSON", text, 0)

    course["id"] = course.get("id") or str(uuid.uuid4())
    course["theme"] = theme
    course["generated_at"] = datetime.now(timezone.utc).isoformat()
    course["model"] = "claude-haiku-4-5"

    return course


def save_course(course: dict):
    COURSES_DIR.mkdir(exist_ok=True)
    course_path = COURSES_DIR / f"{course['id']}.json"
    course_path.write_text(json.dumps(course, indent=2))

    catalog = load_catalog()

    existing_ids = {c["id"] for c in catalog["courses"]}
    if course["id"] not in existing_ids:
        catalog["courses"].append({
            "id": course["id"],
            "title": course.get("title", "Untitled"),
            "description": course.get("description", ""),
            "topic": course.get("topic", ""),
            "theme": course.get("theme"),
            "difficulty": course.get("difficulty", "beginner"),
            "estimated_minutes": course.get("estimated_minutes", 15),
            "tags": course.get("tags", []),
            "generated_at": course.get("generated_at"),
            "node_count": len(course.get("nodes", [])),
            "connection_count": len(course.get("connections", [])),
        })
        catalog["generated"] = len(catalog["courses"])
        save_catalog(catalog)
        label = course["title"]
        if course.get("theme"):
            label += f" [{course['theme']}]"
        print(f"  -> Saved: {label} ({len(course.get('nodes', []))} nodes)", flush=True)
        log_journal(f"SAVED: {label} | id={course['id']} | nodes={len(course.get('nodes', []))}")


def pick_next(topics_data: dict, used: set) -> tuple[str, str | None]:
    """Pick a (topic, theme) pair not yet generated. 70% plain, 30% themed."""
    topics = topics_data.get("topics", [])
    themes = topics_data.get("themes", [])

    plain_candidates = [(t, None) for t in topics if (t, None) not in used]
    themed_candidates = [(t, th) for t in topics for th in themes if (t, th) not in used]

    all_candidates = plain_candidates + (themed_candidates if themes else [])

    if not all_candidates:
        used.clear()
        return (random.choice(topics), None)

    # 30% chance to pick a themed course if any remain
    if themed_candidates and plain_candidates and random.random() < 0.3:
        return random.choice(themed_candidates)
    elif plain_candidates:
        return random.choice(plain_candidates)
    else:
        return random.choice(themed_candidates)


def run():
    COURSES_DIR.mkdir(exist_ok=True)
    log_journal("GENERATOR STARTED")

    catalog = load_catalog()
    used = get_used_combinations(catalog)

    print(f"Course generator started. {len(catalog['courses'])} courses in catalog.", flush=True)

    while True:
        # Reload topics each cycle so edits to topics.json are picked up immediately
        topics_data = load_topics()
        topic, theme = pick_next(topics_data, used)
        used.add((topic, theme))

        try:
            course = generate_course(topic, theme)
            if course:
                save_course(course)
        except json.JSONDecodeError as e:
            print(f"  -> JSON parse error for {topic}: {e}", flush=True)
            log_journal(f"ERROR JSON: {topic} | {e}")
        except subprocess.TimeoutExpired:
            print(f"  -> Claude CLI timeout for {topic}", flush=True)
            log_journal(f"ERROR TIMEOUT: {topic}")
            time.sleep(10)
            continue
        except Exception as e:
            print(f"  -> Error for {topic}: {type(e).__name__}: {e}", flush=True)
            log_journal(f"ERROR: {topic} | {type(e).__name__}: {e}")

        delay = random.uniform(5, 15)
        print(f"  -> Sleeping {delay:.0f}s...", flush=True)
        time.sleep(delay)


if __name__ == "__main__":
    run()
