#!/usr/bin/env python3
"""
SQLite database layer for the Course Store.
Handles users, purchases, sessions, and progress tracking.
"""
import sqlite3
import hashlib
import secrets
import json
import time
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "store.db"

def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()

@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            display_name TEXT,
            bio TEXT,
            avatar_url TEXT,
            created_at TEXT NOT NULL,
            last_login TEXT,
            subscription_tier TEXT DEFAULT 'free',
            subscription_expires TEXT
        );

        CREATE TABLE IF NOT EXISTS courses_store (
            course_id TEXT PRIMARY KEY,
            instructor_id INTEGER REFERENCES users(id),
            price_cents INTEGER NOT NULL DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            is_published INTEGER DEFAULT 0,
            is_featured INTEGER DEFAULT 0,
            category TEXT,
            preview_nodes INTEGER DEFAULT 3,
            total_purchases INTEGER DEFAULT 0,
            total_revenue_cents INTEGER DEFAULT 0,
            avg_rating REAL DEFAULT 0,
            rating_count INTEGER DEFAULT 0,
            published_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            course_id TEXT NOT NULL,
            price_cents INTEGER NOT NULL,
            currency TEXT DEFAULT 'USD',
            payment_method TEXT,
            transaction_id TEXT,
            purchased_at TEXT NOT NULL,
            refunded INTEGER DEFAULT 0,
            refunded_at TEXT,
            UNIQUE(user_id, course_id)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 0,
            course_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            last_active TEXT NOT NULL,
            completed_at TEXT,
            current_node_id TEXT,
            nodes_visited INTEGER DEFAULT 0,
            total_time_seconds INTEGER DEFAULT 0,
            completion_pct REAL DEFAULT 0,
            final_attributes TEXT
        );

        CREATE TABLE IF NOT EXISTS progress_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES sessions(id),
            user_id INTEGER DEFAULT 0,
            course_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            node_type TEXT,
            event_type TEXT NOT NULL,
            event_data TEXT,
            attributes_snapshot TEXT,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            course_id TEXT NOT NULL,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            review_text TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, course_id)
        );

        CREATE TABLE IF NOT EXISTS auth_tokens (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_purchases_user ON purchases(user_id);
        CREATE INDEX IF NOT EXISTS idx_purchases_course ON purchases(course_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_course ON sessions(course_id);
        CREATE INDEX IF NOT EXISTS idx_progress_session ON progress_events(session_id);
        CREATE INDEX IF NOT EXISTS idx_progress_course ON progress_events(course_id);
        CREATE INDEX IF NOT EXISTS idx_progress_user ON progress_events(user_id);
        CREATE INDEX IF NOT EXISTS idx_reviews_course ON reviews(course_id);

        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES users(id),
            instructor_id INTEGER NOT NULL REFERENCES users(id),
            course_id TEXT NOT NULL,
            enrolled_at TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            UNIQUE(student_id, course_id)
        );

        CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id);
        CREATE INDEX IF NOT EXISTS idx_enrollments_instructor ON enrollments(instructor_id);
        CREATE INDEX IF NOT EXISTS idx_enrollments_course ON enrollments(course_id);

        CREATE TABLE IF NOT EXISTS enrollment_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            instructor_id INTEGER NOT NULL REFERENCES users(id),
            course_id TEXT NOT NULL,
            max_uses INTEGER DEFAULT 100,
            uses INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            expires_at TEXT,
            active INTEGER DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_enc_code ON enrollment_codes(code);
        CREATE INDEX IF NOT EXISTS idx_enc_instructor ON enrollment_codes(instructor_id);
        """)

# --- User operations ---

def create_user(email: str, username: str, password: str, role: str = "student", display_name: str = None) -> dict:
    salt = secrets.token_hex(16)
    pw_hash = _hash_password(password, salt)
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO users (email, username, password_hash, salt, role, display_name, created_at) VALUES (?,?,?,?,?,?,?)",
            (email, username, pw_hash, salt, role, display_name or username, now)
        )
        return {"id": cur.lastrowid, "email": email, "username": username, "role": role, "display_name": display_name or username}

def authenticate(email_or_username: str, password: str) -> dict | None:
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM users WHERE email=? OR username=?",
            (email_or_username, email_or_username)
        ).fetchone()
        if not row:
            return None
        if _hash_password(password, row["salt"]) != row["password_hash"]:
            return None
        db.execute("UPDATE users SET last_login=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), row["id"]))
        return dict(row)

def create_token(user_id: int, hours: int = 720) -> str:
    token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    expires = datetime.fromtimestamp(now.timestamp() + hours * 3600, tz=timezone.utc)
    with get_db() as db:
        db.execute(
            "INSERT INTO auth_tokens (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
            (token, user_id, now.isoformat(), expires.isoformat())
        )
    return token

def validate_token(token: str) -> dict | None:
    with get_db() as db:
        row = db.execute(
            "SELECT t.*, u.email, u.username, u.role, u.display_name, u.subscription_tier FROM auth_tokens t JOIN users u ON t.user_id=u.id WHERE t.token=?",
            (token,)
        ).fetchone()
        if not row:
            return None
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            db.execute("DELETE FROM auth_tokens WHERE token=?", (token,))
            return None
        return dict(row)

def get_user(user_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute("SELECT id, email, username, role, display_name, bio, avatar_url, created_at, subscription_tier FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None

# --- Store operations ---

def set_course_store_info(course_id: str, instructor_id: int = None, price_cents: int = 0, category: str = None, is_published: bool = False, is_featured: bool = False, preview_nodes: int = 3):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute("""
            INSERT INTO courses_store (course_id, instructor_id, price_cents, category, is_published, is_featured, preview_nodes, created_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(course_id) DO UPDATE SET
                instructor_id=COALESCE(excluded.instructor_id, instructor_id),
                price_cents=excluded.price_cents,
                category=excluded.category,
                is_published=excluded.is_published,
                is_featured=excluded.is_featured,
                preview_nodes=excluded.preview_nodes
        """, (course_id, instructor_id, price_cents, category, int(is_published), int(is_featured), preview_nodes, now))

def get_store_courses(category: str = None, search: str = None, sort: str = "popular", page: int = 1, per_page: int = 24):
    with get_db() as db:
        where = ["cs.is_published=1"]
        params = []
        if category:
            where.append("cs.category=?")
            params.append(category)
        if search:
            where.append("(cs.course_id LIKE ? OR cs.category LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        order = {"popular": "cs.total_purchases DESC", "newest": "cs.published_at DESC", "price_asc": "cs.price_cents ASC", "price_desc": "cs.price_cents DESC", "rating": "cs.avg_rating DESC"}.get(sort, "cs.total_purchases DESC")

        where_sql = " AND ".join(where)
        offset = (page - 1) * per_page

        rows = db.execute(f"""
            SELECT cs.*, u.display_name as instructor_name
            FROM courses_store cs
            LEFT JOIN users u ON cs.instructor_id=u.id
            WHERE {where_sql}
            ORDER BY {order}
            LIMIT ? OFFSET ?
        """, params + [per_page, offset]).fetchall()

        total = db.execute(f"SELECT COUNT(*) FROM courses_store cs WHERE {where_sql}", params).fetchone()[0]
        return {"courses": [dict(r) for r in rows], "total": total, "page": page, "per_page": per_page}

def purchase_course(user_id: int, course_id: str, price_cents: int, payment_method: str = "card") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    tx_id = f"tx_{secrets.token_hex(12)}"
    with get_db() as db:
        db.execute(
            "INSERT INTO purchases (user_id, course_id, price_cents, payment_method, transaction_id, purchased_at) VALUES (?,?,?,?,?,?)",
            (user_id, course_id, price_cents, payment_method, tx_id, now)
        )
        db.execute("UPDATE courses_store SET total_purchases=total_purchases+1, total_revenue_cents=total_revenue_cents+? WHERE course_id=?", (price_cents, course_id))
        return {"transaction_id": tx_id, "course_id": course_id, "price_cents": price_cents}

def has_purchased(user_id: int, course_id: str) -> bool:
    with get_db() as db:
        row = db.execute("SELECT 1 FROM purchases WHERE user_id=? AND course_id=? AND refunded=0", (user_id, course_id)).fetchone()
        return row is not None

def get_user_purchases(user_id: int) -> list:
    with get_db() as db:
        return [dict(r) for r in db.execute("SELECT * FROM purchases WHERE user_id=? AND refunded=0 ORDER BY purchased_at DESC", (user_id,)).fetchall()]

# --- Session / Progress tracking ---

def start_session(user_id: int, course_id: str, start_node_id: str = None) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO sessions (user_id, course_id, started_at, last_active, current_node_id) VALUES (?,?,?,?,?)",
            (user_id, course_id, now, now, start_node_id)
        )
        return cur.lastrowid

def record_progress(session_id: int, user_id: int, course_id: str, node_id: str, node_type: str, event_type: str, event_data: dict = None, attributes: dict = None):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO progress_events (session_id, user_id, course_id, node_id, node_type, event_type, event_data, attributes_snapshot, timestamp) VALUES (?,?,?,?,?,?,?,?,?)",
            (session_id, user_id, course_id, node_id, node_type, event_type, json.dumps(event_data) if event_data else None, json.dumps(attributes) if attributes else None, now)
        )
        db.execute("UPDATE sessions SET last_active=?, current_node_id=?, nodes_visited=nodes_visited+1 WHERE id=?", (now, node_id, session_id))

def complete_session(session_id: int, final_attributes: dict = None, completion_pct: float = 100):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        session = db.execute("SELECT started_at FROM sessions WHERE id=?", (session_id,)).fetchone()
        total_time = 0
        if session:
            start = datetime.fromisoformat(session["started_at"])
            total_time = int((datetime.now(timezone.utc) - start).total_seconds())
        db.execute(
            "UPDATE sessions SET completed_at=?, total_time_seconds=?, completion_pct=?, final_attributes=? WHERE id=?",
            (now, total_time, completion_pct, json.dumps(final_attributes) if final_attributes else None, session_id)
        )

# --- Analytics (for instructors) ---

def get_course_analytics(course_id: str) -> dict:
    with get_db() as db:
        sessions = db.execute("SELECT * FROM sessions WHERE course_id=?", (course_id,)).fetchall()
        total_sessions = len(sessions)
        completed = [s for s in sessions if s["completed_at"]]
        avg_time = sum(s["total_time_seconds"] for s in completed) / len(completed) if completed else 0
        avg_completion = sum(s["completion_pct"] for s in sessions) / total_sessions if total_sessions else 0

        # Node visit frequency
        node_visits = db.execute("""
            SELECT node_id, node_type, COUNT(*) as visits,
                   COUNT(DISTINCT user_id) as unique_users
            FROM progress_events WHERE course_id=?
            GROUP BY node_id ORDER BY visits DESC
        """, (course_id,)).fetchall()

        # Decision distribution
        decisions = db.execute("""
            SELECT node_id, event_data FROM progress_events
            WHERE course_id=? AND event_type='decision'
        """, (course_id,)).fetchall()
        decision_map = {}
        for d in decisions:
            nid = d["node_id"]
            data = json.loads(d["event_data"]) if d["event_data"] else {}
            choice = data.get("choice", "unknown")
            if nid not in decision_map:
                decision_map[nid] = {}
            decision_map[nid][choice] = decision_map[nid].get(choice, 0) + 1

        # Path analysis - most common paths
        path_events = db.execute("""
            SELECT session_id, GROUP_CONCAT(node_id, '->') as path
            FROM progress_events WHERE course_id=?
            GROUP BY session_id ORDER BY session_id
        """, (course_id,)).fetchall()

        # Attribute outcomes
        attr_outcomes = db.execute("""
            SELECT final_attributes FROM sessions
            WHERE course_id=? AND final_attributes IS NOT NULL
        """, (course_id,)).fetchall()
        avg_attrs = {}
        if attr_outcomes:
            all_attrs = [json.loads(a["final_attributes"]) for a in attr_outcomes]
            keys = set()
            for a in all_attrs:
                keys.update(a.keys())
            for k in keys:
                vals = [a.get(k, 0) for a in all_attrs]
                avg_attrs[k] = round(sum(vals) / len(vals), 1)

        # Recent students (LEFT JOIN to handle anonymous/guest sessions)
        recent = db.execute("""
            SELECT s.*, u.username, u.display_name
            FROM sessions s LEFT JOIN users u ON s.user_id=u.id
            WHERE s.course_id=? ORDER BY s.last_active DESC LIMIT 20
        """, (course_id,)).fetchall()

        return {
            "course_id": course_id,
            "total_sessions": total_sessions,
            "completed_sessions": len(completed),
            "completion_rate": round(len(completed) / total_sessions * 100, 1) if total_sessions else 0,
            "avg_time_seconds": round(avg_time),
            "avg_completion_pct": round(avg_completion, 1),
            "node_visits": [dict(n) for n in node_visits],
            "decision_distribution": decision_map,
            "common_paths": [dict(p) for p in path_events[:20]],
            "avg_final_attributes": avg_attrs,
            "recent_students": [dict(r) for r in recent],
        }

def get_student_analytics(user_id: int) -> dict:
    with get_db() as db:
        sessions = db.execute("SELECT * FROM sessions WHERE user_id=? ORDER BY last_active DESC", (user_id,)).fetchall()
        purchases = db.execute("SELECT * FROM purchases WHERE user_id=? AND refunded=0", (user_id,)).fetchall()
        completed = [s for s in sessions if s["completed_at"]]

        return {
            "total_courses_purchased": len(purchases),
            "total_sessions": len(sessions),
            "completed_sessions": len(completed),
            "total_time_seconds": sum(s["total_time_seconds"] for s in sessions),
            "sessions": [dict(s) for s in sessions[:50]],
        }

def get_instructor_dashboard(instructor_id: int) -> dict:
    with get_db() as db:
        courses = db.execute("SELECT * FROM courses_store WHERE instructor_id=?", (instructor_id,)).fetchall()
        total_revenue = sum(c["total_revenue_cents"] for c in courses)
        total_purchases = sum(c["total_purchases"] for c in courses)

        # Per-course stats
        course_stats = []
        for c in courses:
            sessions = db.execute("SELECT COUNT(*) as cnt, AVG(completion_pct) as avg_comp FROM sessions WHERE course_id=?", (c["course_id"],)).fetchone()
            course_stats.append({
                **dict(c),
                "total_sessions": sessions["cnt"],
                "avg_completion": round(sessions["avg_comp"] or 0, 1),
            })

        return {
            "instructor_id": instructor_id,
            "total_courses": len(courses),
            "total_revenue_cents": total_revenue,
            "total_purchases": total_purchases,
            "courses": course_stats,
        }

def add_review(user_id: int, course_id: str, rating: int, text: str = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO reviews (user_id, course_id, rating, review_text, created_at) VALUES (?,?,?,?,?) ON CONFLICT(user_id, course_id) DO UPDATE SET rating=excluded.rating, review_text=excluded.review_text",
            (user_id, course_id, rating, text, now)
        )
        avg = db.execute("SELECT AVG(rating) as avg, COUNT(*) as cnt FROM reviews WHERE course_id=?", (course_id,)).fetchone()
        db.execute("UPDATE courses_store SET avg_rating=?, rating_count=? WHERE course_id=?", (round(avg["avg"], 2), avg["cnt"], course_id))
        return {"rating": rating, "avg_rating": round(avg["avg"], 2), "total_reviews": avg["cnt"]}

# --- Enrollment operations ---

def enroll_student(student_id: int, instructor_id: int, course_id: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO enrollments (student_id, instructor_id, course_id, enrolled_at, status) VALUES (?,?,?,?,'active') ON CONFLICT(student_id, course_id) DO UPDATE SET status='active', enrolled_at=excluded.enrolled_at",
            (student_id, instructor_id, course_id, now)
        )
    return {"student_id": student_id, "course_id": course_id, "enrolled_at": now}

def unenroll_student(student_id: int, course_id: str) -> bool:
    with get_db() as db:
        db.execute("UPDATE enrollments SET status='inactive' WHERE student_id=? AND course_id=?", (student_id, course_id))
    return True

def is_enrolled(student_id: int, course_id: str) -> bool:
    with get_db() as db:
        row = db.execute("SELECT 1 FROM enrollments WHERE student_id=? AND course_id=? AND status='active'", (student_id, course_id)).fetchone()
    return row is not None

def get_student_enrollments(student_id: int) -> list:
    with get_db() as db:
        rows = db.execute("""
            SELECT e.*, u.display_name as instructor_name, u.email as instructor_email
            FROM enrollments e JOIN users u ON e.instructor_id=u.id
            WHERE e.student_id=? AND e.status='active' ORDER BY e.enrolled_at DESC
        """, (student_id,)).fetchall()
    return [dict(r) for r in rows]

def get_instructor_enrollments(instructor_id: int) -> list:
    with get_db() as db:
        rows = db.execute("""
            SELECT e.*, u.display_name as student_name, u.email as student_email, u.username
            FROM enrollments e JOIN users u ON e.student_id=u.id
            WHERE e.instructor_id=? AND e.status='active' ORDER BY e.enrolled_at DESC
        """, (instructor_id,)).fetchall()
    return [dict(r) for r in rows]

def get_course_enrollment_count(course_id: str) -> int:
    with get_db() as db:
        row = db.execute("SELECT COUNT(*) FROM enrollments WHERE course_id=? AND status='active'", (course_id,)).fetchone()
    return row[0] if row else 0

# --- Enrollment Code operations ---

def create_enrollment_code(instructor_id: int, course_id: str, max_uses: int = 100) -> dict:
    """Generate a short, human-readable enrollment code for a course."""
    code = secrets.token_hex(3).upper()  # e.g. A3F9C2
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        # Ensure uniqueness
        while db.execute("SELECT 1 FROM enrollment_codes WHERE code=?", (code,)).fetchone():
            code = secrets.token_hex(3).upper()
        db.execute(
            "INSERT INTO enrollment_codes (code, instructor_id, course_id, max_uses, created_at) VALUES (?,?,?,?,?)",
            (code, instructor_id, course_id, max_uses, now)
        )
    return {"code": code, "course_id": course_id, "max_uses": max_uses}

def redeem_enrollment_code(code: str, student_id: int) -> dict:
    """Student redeems an enrollment code. Returns enrollment info or raises ValueError."""
    code = code.strip().upper()
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM enrollment_codes WHERE code=? AND active=1", (code,)
        ).fetchone()
        if not row:
            raise ValueError("Invalid or expired enrollment code.")
        if row["uses"] >= row["max_uses"]:
            raise ValueError("This enrollment code has reached its maximum uses.")
        # Enroll the student
        now = datetime.now(timezone.utc).isoformat()
        try:
            db.execute(
                "INSERT INTO enrollments (student_id, instructor_id, course_id, enrolled_at, status) VALUES (?,?,?,?,?)",
                (student_id, row["instructor_id"], row["course_id"], now, "active")
            )
        except Exception:
            raise ValueError("You are already enrolled in this course.")
        db.execute("UPDATE enrollment_codes SET uses=uses+1 WHERE code=?", (code,))
        # Get instructor name
        instr = db.execute("SELECT display_name, username FROM users WHERE id=?", (row["instructor_id"],)).fetchone()
        instr_name = (instr["display_name"] or instr["username"]) if instr else "Unknown"
    return {"course_id": row["course_id"], "instructor_name": instr_name}

def get_instructor_codes(instructor_id: int) -> list:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM enrollment_codes WHERE instructor_id=? ORDER BY created_at DESC",
            (instructor_id,)
        ).fetchall()
    return [dict(r) for r in rows]

# Initialize on import
init_db()
