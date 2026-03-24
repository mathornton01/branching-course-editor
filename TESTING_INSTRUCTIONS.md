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

## 🔧 **Connection Fix Testing Procedure** (Today's Focus)

### 🐛 **Original Issue:**
- Clicking the **dot** (connection point) → Purple flash (works)
- Clicking the **node** itself (title/text/body) → No flash at all (broken)

### 🧪 **Test Procedure:**
1. **Load Sample Course**: Go to http://localhost:8080/course-editor-enhanced.html and load "Sample Branching Course"
2. **Enter Connection Mode**: Click the "Add Connection" button (should turn blue when active)
3. **Test Dot Click**: Click on any connection point (small circle) → Should see:
   - 🟢 Green border (global mousedown)  
   - 🔴 Red background (nodesContainer mousedown)
   - 🟣 Blue violet flash (listeners attached) ← This is the "purple" they saw
   - 🟡 Yellow flash (startConnection reached)
   - etc.
4. **Test Node Click**: Click anywhere on a NODE itself (title, text, or body area) → Should now see:
   - 🟢 Green border (global mousedown)  
   - 🔴 Red background (nodesContainer mousedown) 
   - 🟡 **Yellow background** (got connection point from node) ← **THIS IS THE FIX**
   - 🟣 Blue violet flash (listeners attached)
   - 🟡 Yellow flash (startConnection reached)
   - etc.

### 📊 **Success Criteria:**
- **Before Fix**: Node clicks showed ONLY green border (global mousedown works) but NO red background (nodesContainer mousedown not bubbling up)  
- **After Fix**: Node clicks show green → red → yellow → blue violet → yellow sequence (full connection flow works)

### 🎨 **Color Meanings:**
- 🟢 Green border = Any mousedown on page detected
- 🔴 Red background = Mousedown on nodesContainer detected  
- 🟡 Yellow background = Successfully got connection point from node (our fix!)
- 🟣 Blue violet = Mousemove/mouseup listeners attached
- 🟡 Yellow flash = startConnection function reached
- 🔵 Cyan flash = Temporary connection line created
- 🟢 Light green = Mouse up detected
- 🟣 Magenta = Temporary line removed
- 🟢 Permanent green = Connection successfully created

Report what color sequence you see when clicking nodes vs dots in connection mode!