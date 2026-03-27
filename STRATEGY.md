# Branching Course Platform -- Strategy Document

Updated: 2026-03-27

## Current State

The editor (course-editor-enhanced.html) is a fully functional single-page canvas app served via Python HTTP server on DGX Spark. It supports:

- Visual node-based course authoring (Content, Decision, Quiz, Condition, Page Link, End nodes)
- Drag-and-drop from toolbar onto canvas
- Connection creation between nodes via output dots
- Link Drag (rope/tether physics) toggle
- Downstream Drag (rigid group move) toggle
- Node Repulsion toggle (nodes push apart to avoid overlap)
- Pattern insertion (pre-built node configurations)
- Multi-page course support
- Course save/load via API server (YAML-based)
- Auto-layout engine with snap-to-grid
- Settings panel with zoom, grid, physics toggles

Supporting infrastructure:
- API server (course_api_server.py) for CRUD operations
- Course generator (course_generator.py) for AI-assisted course creation
- Course improver (course_improver.py) for AI-assisted quality improvements
- Course auditor and deduplicator for maintenance
- Player (player.html) for course playback
- GitHub repo: github.com/mathornton01/branching-course-editor

## Roadmap

### Phase A: Player Enhancement (next)

Goal: Make the player a first-class citizen with deep editor integration.

1. Editor-to-Player hooks
   - "Preview" button in editor opens player with current course loaded
   - Deep links: editor node click jumps to that point in player, and vice versa
   - Live reload: player auto-refreshes when editor saves

2. Customer-facing player
   - Clean, distraction-free UI for end-users (learners)
   - Progress tracking (which nodes visited, decisions made)
   - Bookmarking / resume support
   - Mobile-responsive layout
   - Embeddable via iframe for LMS integration

### Phase B: Database Structure

Goal: Move from flat YAML files to a proper database for scalability and multi-user support.

1. Schema design
   - Courses table (id, title, description, author, created, updated, status)
   - Nodes table (id, course_id, type, position, content, metadata)
   - Connections table (id, source_node, target_node, label, condition)
   - Pages table (id, course_id, title, ordering)
   - User progress table (user_id, course_id, current_node, history, score)
   - Analytics table (events, timestamps, aggregations)

2. Migration path
   - Keep YAML import/export for portability
   - Add SQLite for local development, PostgreSQL for production
   - API server switches to DB-backed storage

### Phase C: Multi-user and Collaboration

1. User accounts and authentication
2. Course ownership and sharing permissions
3. Version history per course
4. Real-time collaborative editing (WebSocket)

### Phase D: LMS Integration

1. SCORM/xAPI export
2. LTI provider integration
3. Grade passback
4. Completion certificates

## Technical Stack

Current:
- Frontend: Vanilla HTML/CSS/JS (single-file SPA)
- Backend: Python (HTTP server + Flask-style API)
- Storage: YAML files on disk
- Hosting: DGX Spark (local network)

Target:
- Frontend: Same SPA approach (works well, no framework needed yet)
- Backend: Python FastAPI
- Database: SQLite (dev) / PostgreSQL (prod)
- Hosting: DGX Spark local, cloud deployment later

## Key Decisions

- Keep the single-file SPA architecture -- it's simple, portable, and works
- YAML stays as import/export format even after DB migration
- Player and editor share the same data layer but are separate HTML files
- AI-assisted course generation is a differentiator -- keep investing in it

## GitHub Repository

Repo: https://github.com/mathornton01/branching-course-editor
Branch: main
