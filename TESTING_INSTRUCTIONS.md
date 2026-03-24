# Testing Instructions for Branching Course Editor

## Available Interfaces

1. **Enhanced Course Editor** (with drag-and-drop, node editing, and connection creation)
   - URL: http://localhost:8080/course-editor-enhanced.html
   - Features:
     - Drag-and-drop node positioning
     - Node selection and property editing (title, type, content)
     - Connection creation between nodes via connection points
     - Real-time visual feedback
     - Course loading/saving (API integrated)

2. **Original Course Editor** (basic version)
   - URL: http://localhost:8080/course-editor.html
   - Features:
     - Course listing and selection
     - Basic course editing
     - Template browser
     - Course structure visualization

3. **API Server** (running on port 8001)
   - URL: http://localhost:8001
   - Endpoints:
     - GET /api/courses - List all courses
     - GET /api/courses/{id} - Get specific course
     - POST /api/courses - Create new course
     - PUT /api/courses/{id} - Update course
     - DELETE /api/courses/{id} - Delete course
     - GET /api/templates - List templates
     - GET /api/health - Health check

## How to Test the Enhanced Editor

1. **Load a Course**:
   - Use the dropdown menu to select "Sample Branching Course"
   - Click "Load Course" button

2. **Select and Edit Nodes**:
   - Click on any node to select it (will show blue ring)
   - Edit the title, type, or content in the properties panel on the right
   - Changes update in real-time

3. **Create Connections**:
   - Click and drag from the small circle (connection point) at the bottom of a node
   - Drag to another node's connection point to create a connection
   - You'll see a dashed line while dragging
   - Release to create the connection (success indicator will appear)

4. **Add New Nodes**:
   - Click the "Add Node" button to create new nodes
   - New nodes appear at position (100, 100) and can be dragged

5. **Save Course**:
   - Click "Save Course" to save your changes (currently shows alert, in real implementation would POST to API)

## Current Capabilities Implemented

✅ Drag-and-drop node positioning
✅ Node selection and property editing (title, type, content)
✅ Connection creation between nodes
✅ Real-time visual feedback for all interactions
✅ Course loading from API
✅ Node addition
✅ Visual selection indicators
✅ Connection validation (prevents self-loops, duplicates)

## Next Features to Implement

- Connection editing (conditions, labels) in properties panel
- Decision tree logic (path validation, loop detection)
- Basic progress tracking
- Course export/import functionality
- Enhanced template system

## Server Information

- Enhanced Editor: http://localhost:8080/course-editor-enhanced.html
- Basic Editor: http://localhost:8080/course-editor.html  
- API Server: http://localhost:8001 (already running)
- Editor Web Server: http://localhost:8080 (serve-editor.py)

To stop the editor web server, find the process and kill it, or press Ctrl+C in the terminal where it's running.