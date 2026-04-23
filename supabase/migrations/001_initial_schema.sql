-- ============================================================
-- Branching Course Editor - Supabase PostgreSQL Schema
-- Migrated from SQLite (store_db.py)
-- ============================================================

-- Enable UUID extension (available by default in Supabase)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Users ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    salt            TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'student',
    display_name    TEXT,
    bio             TEXT,
    avatar_url      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login      TIMESTAMPTZ,
    subscription_tier   TEXT DEFAULT 'free',
    subscription_expires TIMESTAMPTZ
);

-- ── Courses Store ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS courses_store (
    course_id           TEXT PRIMARY KEY,
    instructor_id       INTEGER REFERENCES users(id),
    price_cents         INTEGER NOT NULL DEFAULT 0,
    currency            TEXT DEFAULT 'USD',
    is_published        BOOLEAN DEFAULT FALSE,
    is_featured         BOOLEAN DEFAULT FALSE,
    category            TEXT,
    preview_nodes       INTEGER DEFAULT 3,
    total_purchases     INTEGER DEFAULT 0,
    total_revenue_cents INTEGER DEFAULT 0,
    avg_rating          REAL DEFAULT 0,
    rating_count        INTEGER DEFAULT 0,
    published_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Purchases ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS purchases (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    course_id       TEXT NOT NULL,
    price_cents     INTEGER NOT NULL,
    currency        TEXT DEFAULT 'USD',
    payment_method  TEXT,
    transaction_id  TEXT,
    purchased_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    refunded        BOOLEAN DEFAULT FALSE,
    refunded_at     TIMESTAMPTZ,
    UNIQUE(user_id, course_id)
);

-- ── Sessions ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER DEFAULT 0,
    course_id           TEXT NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    current_node_id     TEXT,
    nodes_visited       INTEGER DEFAULT 0,
    total_time_seconds  INTEGER DEFAULT 0,
    completion_pct      REAL DEFAULT 0,
    final_attributes    JSONB
);

-- ── Progress Events ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS progress_events (
    id                  SERIAL PRIMARY KEY,
    session_id          INTEGER NOT NULL REFERENCES sessions(id),
    user_id             INTEGER DEFAULT 0,
    course_id           TEXT NOT NULL,
    node_id             TEXT NOT NULL,
    node_type           TEXT,
    event_type          TEXT NOT NULL,
    event_data          JSONB,
    attributes_snapshot JSONB,
    timestamp           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Reviews ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reviews (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    course_id       TEXT NOT NULL,
    rating          INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
    review_text     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, course_id)
);

-- ── Auth Tokens ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS auth_tokens (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);

-- ── Enrollments ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS enrollments (
    id              SERIAL PRIMARY KEY,
    student_id      INTEGER NOT NULL REFERENCES users(id),
    instructor_id   INTEGER NOT NULL REFERENCES users(id),
    course_id       TEXT NOT NULL,
    enrolled_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          TEXT DEFAULT 'active',
    UNIQUE(student_id, course_id)
);

-- ── Enrollment Codes ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS enrollment_codes (
    id              SERIAL PRIMARY KEY,
    code            TEXT UNIQUE NOT NULL,
    instructor_id   INTEGER NOT NULL REFERENCES users(id),
    course_id       TEXT NOT NULL,
    max_uses        INTEGER DEFAULT 100,
    uses            INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    active          BOOLEAN DEFAULT TRUE
);

-- ============================================================
-- Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_purchases_user     ON purchases(user_id);
CREATE INDEX IF NOT EXISTS idx_purchases_course   ON purchases(course_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user      ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_course    ON sessions(course_id);
CREATE INDEX IF NOT EXISTS idx_progress_session   ON progress_events(session_id);
CREATE INDEX IF NOT EXISTS idx_progress_course    ON progress_events(course_id);
CREATE INDEX IF NOT EXISTS idx_progress_user      ON progress_events(user_id);
CREATE INDEX IF NOT EXISTS idx_reviews_course     ON reviews(course_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_student    ON enrollments(student_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_instructor ON enrollments(instructor_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_course     ON enrollments(course_id);
CREATE INDEX IF NOT EXISTS idx_enc_code           ON enrollment_codes(code);
CREATE INDEX IF NOT EXISTS idx_enc_instructor     ON enrollment_codes(instructor_id);

-- ============================================================
-- Row Level Security (RLS) Policies
-- ============================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses_store ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchases ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE progress_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE auth_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE enrollment_codes ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (used by API serverless functions)
-- These policies allow the service_role key full access.
-- The anon key gets read-only access to published courses.

-- Published courses are publicly readable
CREATE POLICY "Public can view published courses"
    ON courses_store FOR SELECT
    USING (is_published = TRUE);

-- Service role bypass (applied via supabase service key in API functions)
-- Supabase automatically grants service_role full access when RLS is enabled,
-- so we only need explicit policies for the anon key.

-- Users can read their own data
CREATE POLICY "Users can view own profile"
    ON users FOR SELECT
    USING (auth.uid()::text = id::text);

-- Users can read their own purchases
CREATE POLICY "Users can view own purchases"
    ON purchases FOR SELECT
    USING (auth.uid()::text = user_id::text);

-- Users can read their own sessions
CREATE POLICY "Users can view own sessions"
    ON sessions FOR SELECT
    USING (auth.uid()::text = user_id::text);

-- Users can read their own progress
CREATE POLICY "Users can view own progress"
    ON progress_events FOR SELECT
    USING (auth.uid()::text = user_id::text);

-- Users can read and write their own reviews
CREATE POLICY "Users can manage own reviews"
    ON reviews FOR ALL
    USING (auth.uid()::text = user_id::text);

-- Enrollment codes are publicly readable (needed to redeem)
CREATE POLICY "Public can view active enrollment codes"
    ON enrollment_codes FOR SELECT
    USING (active = TRUE);

-- Users can view their own enrollments
CREATE POLICY "Users can view own enrollments"
    ON enrollments FOR SELECT
    USING (auth.uid()::text = student_id::text);
