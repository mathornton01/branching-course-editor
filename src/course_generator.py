#!/usr/bin/env python3
"""
Background course generator — uses claude-sonnet-4-6 via Claude CLI to continuously generate
rich branching courses with attributes, variables, and exotic layouts.
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

MODEL = "sonnet"
CLAUDE_BIN = "/home/mathornton/.local/bin/claude"

SYSTEM_PROMPT = """You are a world-class instructional designer and interactive storyteller. Generate a rich, sophisticated branching course as valid JSON.

=== NODE TYPES (use ALL that apply — variety is key!) ===

content: Information display with rich markdown (5-10 sentences, use headers, bold, lists, code blocks as appropriate)
  {id, type:"content", title, content (markdown), position:{x,y}, attribute_effects:{attr:delta,...}, set_variables:{var:val,...}}

example: Detailed worked example with step-by-step breakdown (5-8 sentences)
  {id, type:"example", title, content (markdown), position:{x,y}, attribute_effects:{attr:delta,...}}

assessment: Scored quiz with 2-4 questions, routing based on score
  {id, type:"assessment", title, content, questions:[...], passing_score:80, success_target:"nX", failure_target:"nY", position:{x,y}}
  questions format: [{question, options:[str,str,str,str], correct_index:0-3, feedback:[str,str,str,str], explanation:"..."}]

practice: Like assessment but for reinforcement after failure
  {id, type:"practice", title, content, questions:[...], passing_score:60, success_target:"nX", failure_target:"nY", position:{x,y}}

decision: Meaningful learner choices that shape the experience
  {id, type:"decision", title, content, choices:[{label, next}], position:{x,y}}

random: Uniform random branch — use for unpredictable events, varied practice, surprise elements
  {id, type:"random", title, content, position:{x,y}}

weighted: Probability-weighted branch — use for realistic scenario simulations
  {id, type:"weighted", title, content, position:{x,y}}

condition: Routes based on learner variables/score
  {id, type:"condition", title, content, condition:"variable_name", default_target:"nX", position:{x,y}}

gate: Blocks progress until condition met
  {id, type:"gate", title, content, condition:"expression", default_target:"nX", position:{x,y}}

end: Terminal node — include a summary of what was learned and personalized feedback
  {id, type:"end", title, content, position:{x,y}}

=== CONNECTIONS ===
{id, source, target, label, type:"default"|"conditional"|"weighted"|"random", weight:N (for weighted), condition:"expr" (for conditional)}

=== ATTRIBUTE SYSTEM ===
Nodes can modify learner attributes via attribute_effects. Track things like:
- knowledge, confidence, experience, skill_level, creativity, critical_thinking
Use these to create condition nodes that route based on accumulated attributes.
Example: A content node about advanced theory might have attribute_effects:{knowledge:10, critical_thinking:5}

=== VARIABLE SYSTEM ===
Nodes can set variables via set_variables:{var:val}. Use for tracking choices, paths taken, etc.
Condition nodes evaluate these: "knowledge >= 20", "path == 'research'", etc.

=== POSITION SYSTEM ===
Give every node a position:{x, y} for visual layout. Use a tree-like layout:
- Start nodes: x=100
- Each subsequent layer: +300 x
- Vertical spacing: ~200 between parallel nodes
- Branch out vertically, converge back

=== OUTPUT FORMAT ===
Output ONLY raw valid JSON (no markdown fences):
{"id":"<uuid>","title":"...","description":"...","topic":"...","theme":null,"difficulty":"beginner|intermediate|advanced","estimated_minutes":<n>,"tags":[...],"nodes":[...],"connections":[...]}

=== STRUCTURE TEMPLATES — pick ONE or COMBINE elements from multiple ===

A) SKILL TREE (learner chooses path, branches merge)
   decision(intro) → [branch A: content→example→assessment] AND [branch B: content→example→assessment]
   → condition(score-check) → [high: advanced content → end] [low: review → end]
   15-18 nodes. Include attribute_effects on content nodes.

B) MASTERY LADDER (sequential with fail loops and random practice)
   content→assessment [fail→random(picks 1 of 3 practice variants)→back to assessment] [pass→next level]
   → gate(must pass 2 assessments) → synthesis → end
   14-18 nodes. Use random nodes for practice variety.

C) DIAGNOSTIC BRANCH (opening quiz routes to appropriate depth)
   assessment(diagnostic) → condition(score-router) → [beginner path | intermediate path | advanced path]
   Each path has: content→example→practice→decision(explore more?)
   16-20 nodes. Use condition node with score thresholds.

D) EXPLORE & CONVERGE (multiple topic areas with decisions)
   intro → decision(3 choices) → [each: content→example→assessment with attribute_effects]
   → condition(checks accumulated knowledge) → [synthesis or remediation] → end
   18-22 nodes. Heavy use of attribute_effects.

E) SCENARIO TREE (narrative with weighted random events)
   content(setup) → decision → [path A with weighted random encounters] [path B with different challenges]
   Multiple decision points, 3-4 distinct endings reflecting cumulative choices
   18-24 nodes. Use weighted nodes for realistic drama.

F) ASSESSMENT PYRAMID (escalating challenge with gates)
   easy_assessment → condition(score) → [high: skip ahead via gate] [medium: standard path] [low: remediation]
   Each tier has content + examples + practice. Gate at top requires knowledge >= threshold.
   16-20 nodes. Use gates and conditions heavily.

G) ADVENTURE PATH (narrative-driven with all node types)
   Combine content, decisions, random events, weighted outcomes, gates, and assessments
   into a cohesive narrative. Variables track story state. Multiple endings.
   20-25 nodes. Showcase everything.

=== CRITICAL RULES ===
- Generate 15-25 nodes (NOT 7-9 like a simple course)
- Use at LEAST 4 different node types per course
- Include at least one random OR weighted node per course
- Add attribute_effects to at least 5 content/example nodes
- Write REAL, substantive educational content — paragraphs, not sentences
- Content nodes should be 5-10 sentences with markdown formatting (headers, lists, bold, code)
- Assessment questions should be thoughtful with detailed feedback and explanations
- Decision choices should be meaningful and lead to genuinely different experiences
- Every connection needs an id (c1, c2...) and proper type field
- All nodes must be reachable; every non-end node must have outgoing connections
- If theme given, weave it deeply into every piece of content
- Include position:{x,y} on every node for visual layout
- End nodes should summarize what was learned, reference the path taken"""


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
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr[:200]}")
    return result.stdout.strip()


STRUCTURE_TEMPLATES = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
_template_idx = [0]

def generate_course(topic: str, theme: str | None = None) -> dict | None:
    # Rotate through structure templates so output varies
    template = STRUCTURE_TEMPLATES[_template_idx[0] % len(STRUCTURE_TEMPLATES)]
    _template_idx[0] += 1
    template_hint = f"\nUse structure template {template} from the system prompt.\n"

    theme_line = ""
    if theme:
        theme_line = f"""Theme: {theme}
Every example, analogy, scenario, case study, and practice question MUST be set in the context of {theme}.
The content should teach {topic} entirely through the lens of {theme}.
"""

    prompt = f"""Create a sophisticated, feature-rich branching course on: {topic}
{template_hint}
{theme_line}
MANDATORY REQUIREMENTS (courses missing these will be REJECTED):

1. NODE COUNT: Generate 18-28 nodes. NOT 7-10. NOT 12. At least 18.
2. NODE TYPE VARIETY: Use at least 5 DIFFERENT node types from: content, example, assessment, practice, decision, random, weighted, condition, gate, end
3. ATTRIBUTE EFFECTS: Add attribute_effects:{{}} on at LEAST 6 content or example nodes.
   Use attributes like: knowledge, confidence, experience, skill_level, creativity, critical_thinking, intuition, wisdom
   Example: "attribute_effects": {{"knowledge": 10, "confidence": 5}}
4. VARIABLES: Use set_variables on at LEAST 3 nodes to track learner state.
   Example: "set_variables": {{"path": "analytical", "depth": "advanced"}}
5. RANDOMNESS: Include at least ONE random node AND one weighted node with explicit weight values on connections.
6. CONDITIONS: Include at least one condition or gate node that evaluates accumulated attributes.
   Example gate: "condition": "knowledge >= 25"
7. ASSESSMENTS: At least one assessment with 3+ questions, each with 4 options, per-option feedback[], and explanation.
8. DECISIONS: At least 2 decision nodes with 2-3 meaningful choices each.
9. CONTENT DEPTH: Content/example nodes must have 5-10 sentences with markdown (headers, bold, lists, code if relevant).
10. MULTIPLE ENDINGS: At least 2 different end nodes reflecting different paths.
11. POSITIONS: Every node needs position:{{x,y}} in a tree layout (x+300 per layer, y spacing ~200).
12. CONNECTIONS: Every connection needs id, source, target, type, and label.

IMPORTANT: Output ONLY valid JSON. No explanation, no markdown fences, just raw JSON starting with {{ and ending with }}."""

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
    course["model"] = "claude-sonnet-4-6"

    # Quality validation — reject shallow courses
    nodes = course.get("nodes", [])
    node_types = set(n.get("type") for n in nodes)
    has_attrs = sum(1 for n in nodes if n.get("attribute_effects"))
    has_vars = sum(1 for n in nodes if n.get("set_variables"))

    if len(nodes) < 14:
        print(f"  -> REJECTED: only {len(nodes)} nodes (need 14+)", flush=True)
        log_journal(f"REJECTED: {label} | only {len(nodes)} nodes")
        return None
    if len(node_types) < 4:
        print(f"  -> REJECTED: only {len(node_types)} node types (need 4+)", flush=True)
        log_journal(f"REJECTED: {label} | only {len(node_types)} types")
        return None
    if has_attrs < 3:
        print(f"  -> REJECTED: only {has_attrs} nodes with attribute_effects (need 3+)", flush=True)
        log_journal(f"REJECTED: {label} | only {has_attrs} attribute nodes")
        return None

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
