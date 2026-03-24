# Branching Courses System

A system for implementing branching courses with template-driven design for creating adaptive learning experiences.

## Project Structure
- `PROJECT_OVERVIEW.md` - High-level project vision and goals
- `STRATEGY.md` - Detailed strategy, timeline, and approach
- `TASK_LIST.md` - Initial task breakdown by phase and week
- `src/` - Source code implementation
  - `BRANCHING_FORMAT.md` - Specification for the branching course YAML format
  - `sample-course.yaml` - Example course in the branching format
  - `branching_parser.py` - Python parser for converting YAML to traversable web structure
  - `test_parser.py` - Test script demonstrating parser functionality

## Getting Started
This project has progressed beyond planning into initial implementation. We have:

1. **Defined a branching course format** (YAML-based) for describing adaptive learning paths
2. **Implemented a parser** that converts YAML course definitions into traversable web structures
3. **Created a sample course** demonstrating the format's capabilities
4. **Built traversal logic** for navigating branching paths based on user choices

## What We've Implemented This Turn

### Branching Course Format
- YAML-based format for human-readable course definitions
- Supports content nodes, decision nodes, and assessment nodes
- Includes conditional branching based on user choices and assessment scores
- Visual positioning data for course mapping interfaces
- Extensible design for future enhancements

### Parser Implementation
- Python parser (`branching_parser.py`) that reads YAML files
- Converts to JSON-serializable web-traversable structure
- Includes traversal helpers for efficient navigation
- Logic for evaluating conditions (option selections, assessment scores)
- Start/end node detection for course flow analysis

### REST API Implementation
- FastAPI-based REST API (`api_server.py`) for course management
- Full CRUD operations for courses (Create, Read, Update, Delete)
- Course structure retrieval and parsing endpoints
- Automatic loading of sample course on startup
- Interactive API documentation at `/docs`
- **Template system** with gallery, preview, and application endpoints

### Template System
- Three initial templates: Linear Progression, Binary Choice, Multi-Path Scenario
- Template API endpoints: list, get details, apply to create course
- Automatic template loading from YAML files on startup
- Template-to-course conversion with proper structure preservation

### Course Editor UI
- Interactive HTML/JavaScript course editor (`course-editor.html`)
- Course listing and selection interface
- Real-time course editing (title, description, ID)
- Course structure visualization (nodes and connections)
- Template browser with one-click application
- Responsive design using Tailwind CSS
- Direct API integration for all operations

### Visual Branching Interface (NEW)
- Enhanced course editor with drag-and-drop functionality (`course-editor-enhanced.html`)
- Drag-and-drop node positioning with visual feedback
- Connection rendering between nodes using SVG
- Real-time updates to course structure as nodes are moved
- Node selection and visual indicators during drag operations
- Course saving capability (placeholder for backend integration)
- Connection creation between nodes via drag-from-connection-point interaction
- Visual feedback for connection creation (temporary dashed lines, success indicators)

### Node Properties Panel (NEW)
- Interactive node editing sidebar for modifying node properties
- Title editing with real-time preview
- Node type switching (content, decision, assessment) 
- Content editing with textarea input
- Save/cancel functionality with visual feedback
- Visual selection indicators (blue ring around selected node)

### Sample Course
- Demonstrates learning style branching (visual/auditory/kinesthetic paths)
- Includes assessment with remediation paths
- Shows various connection types and conditions
- Provides realistic example of branching educational content

## Next Steps
1. Review the implemented format and parser in `src/`
2. Examine the sample course (`src/sample-course.yaml`) 
3. Run the test (`python3 src/test_parser.py`) to see the parser in action
4. Begin implementing a simple web interface to display and traverse courses
5. Continue with Phase 1 foundation tasks from TASK_LIST.md:
   - Set up proper development environment
   - Implement basic API endpoints for course management
   - Create initial template system