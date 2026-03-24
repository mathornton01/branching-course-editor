#!/usr/bin/env python3
"""
Simple REST API for Branching Courses System
Provides basic CRUD operations for managing branching courses.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json
import os
from pathlib import Path

# Import our parser
import sys
import yaml
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from branching_parser import parse_branching_course, BranchingCourseParser

app = FastAPI(
    title="Branching Courses API",
    description="API for managing branching courses with adaptive learning paths",
    version="1.0.0"
)

# Configure CORS to allow requests from any origin (development)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins - FIXES CORS for remote access
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Pydantic models for API
class CourseBase(BaseModel):
    id: str
    title: str
    description: str
    version: str = "1.0.0"
    tags: List[str] = []

class CourseCreate(CourseBase):
    pass

class CourseResponse(CourseBase):
    id: str
    title: str
    description: str
    version: str
    tags: List[str]
    # Additional computed fields
    node_count: int
    connection_count: int

class CourseDetailResponse(CourseResponse):
    structure: Dict[str, Any]  # Full parsed course structure

# Template models
class TemplateBase(BaseModel):
    id: str
    name: str
    description: str
    category: str = "basic"

class TemplateResponse(TemplateBase):
    id: str
    name: str
    description: str
    category: str
    structure: List[Dict[str, Any]]  # Template structure (list of nodes)
    connections: List[Dict[str, Any]] = []  # Template connections

# In-memory storage for demo (would be replaced with database)
courses_storage: Dict[str, Dict[str, Any]] = {}
templates_storage: Dict[str, Dict[str, Any]] = {}

# Initialize with sample course
def initialize_sample_data():
    """Load sample course into storage on startup."""
    try:
        sample_path = Path(__file__).parent / "sample-course.yaml"
        if sample_path.exists():
            course_structure = parse_branching_course(str(sample_path))
            course_id = course_structure['course']['id']
            
            # Store simplified course info
            courses_storage[course_id] = {
                'id': course_id,
                'title': course_structure['course']['title'],
                'description': course_structure['course']['description'],
                'version': course_structure['course']['version'],
                'tags': course_structure['course']['tags'],
                'node_count': len(course_structure['nodes']),
                'connection_count': len(course_structure['connections']),
                'structure': course_structure  # Full structure for detail views
            }
            print(f"Loaded sample course: {course_id}")
    except Exception as e:
        print(f"Warning: Could not load sample course: {e}")

# Initialize templates
def initialize_templates():
    """Load template definitions into storage on startup."""
    templates_dir = Path(__file__).parent / "templates"
    if not templates_dir.exists():
        print("Templates directory not found")
        return
        
    template_files = list(templates_dir.glob("*.yaml"))
    print(f"Found {len(template_files)} template files to load")
    
    for template_file in template_files:
        try:
            with open(template_file, 'r') as f:
                template_data = yaml.safe_load(f)
            
            template_id = template_data.get('id')
            if template_id:
                templates_storage[template_id] = {
                    'id': template_id,
                    'name': template_data.get('name', ''),
                    'description': template_data.get('description', ''),
                    'category': template_data.get('category', 'basic'),
                    'structure': template_data.get('structure', []),
                    'connections': template_data.get('connections', [])
                }
                print(f"Loaded template: {template_id}")
        except Exception as e:
            print(f"Warning: Could not load template {template_file}: {e}")

# Load sample data and templates on startup
initialize_sample_data()
initialize_templates()

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Branching Courses API",
        "version": "1.0.0",
        "endpoints": {
            "GET /": "API information",
            "GET /api/courses": "List all courses",
            "POST /api/courses": "Create a new course",
            "GET /api/courses/{course_id}": "Get course details",
            "PUT /api/courses/{course_id}": "Update a course",
            "DELETE /api/courses/{course_id}": "Delete a course",
            "GET /api/courses/{course_id}/structure": "Get full course structure",
            "POST /api/courses/{course_id}/parse": "Parse a YAML course file",
            "GET /api/health": "Health check"
        }
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "courses_loaded": len(courses_storage),
        "templates_loaded": len(templates_storage),
        "timestamp": "2026-03-23T19:23:00Z"
    }

@app.get("/api/courses", response_model=List[CourseResponse])
async def list_courses():
    """List all available courses."""
    return list(courses_storage.values())

@app.post("/api/courses", response_model=CourseResponse)
async def create_course(course: CourseCreate):
    """Create a new course."""
    if course.id in courses_storage:
        raise HTTPException(status_code=400, detail=f"Course with ID '{course.id}' already exists")
    
    # For now, we'll store basic info - full structure would come from file upload
    course_data = {
        'id': course.id,
        'title': course.title,
        'description': course.description,
        'version': course.version,
        'tags': course.tags,
        'node_count': 0,  # Will be updated when structure is added
        'connection_count': 0,
        'structure': None
    }
    
    courses_storage[course.id] = course_data
    return course_data

@app.get("/api/courses/{course_id}", response_model=CourseDetailResponse)
async def get_course(course_id: str):
    """Get details for a specific course."""
    if course_id not in courses_storage:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    
    course_data = courses_storage[course_id]
    return CourseDetailResponse(**course_data)

@app.put("/api/courses/{course_id}", response_model=CourseResponse)
async def update_course(course_id: str, course: CourseCreate):
    """Update an existing course."""
    if course_id not in courses_storage:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    
    # Update the course
    courses_storage[course_id].update({
        'title': course.title,
        'description': course.description,
        'version': course.version,
        'tags': course.tags
    })
    
    return courses_storage[course_id]

@app.delete("/api/courses/{course_id}")
async def delete_course(course_id: str):
    """Delete a course."""
    if course_id not in courses_storage:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    
    deleted_course = courses_storage.pop(course_id)
    return {"message": f"Course '{deleted_course['id']}' deleted successfully"}

@app.get("/api/courses/{course_id}/structure")
async def get_course_structure(course_id: str):
    """Get the full parsed structure of a course."""
    if course_id not in courses_storage:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    
    course_data = courses_storage[course_id]
    if course_data['structure'] is None:
        raise HTTPException(status_code=404, detail=f"No structure available for course: {course_id}")
    
    return course_data['structure']

@app.post("/api/courses/{course_id}/parse")
async def parse_course_file(course_id: str, background_tasks: BackgroundTasks, file_content: str):
    """
    Parse a YAML course file and store it.
    In a real implementation, this would accept file uploads.
    """
    if course_id not in courses_storage:
        raise HTTPException(status_code=404, detail=f"Course not found: {course_id}")
    
    try:
        # Parse the YAML content
        import tempfile
        import yaml
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(file_content)
            temp_path = f.name
        
        parser = BranchingCourseParser()
        course_structure = parser.parse_file(temp_path)
        
        # Clean up temp file
        os.unlink(temp_path)
        
        # Update storage with parsed structure
        courses_storage[course_id].update({
            'structure': course_structure,
            'node_count': len(course_structure['nodes']),
            'connection_count': len(course_structure['connections'])
        })
        
        # Clean up temp file
        os.unlink(temp_path)
        
        return {
            "message": f"Course {course_id} parsed successfully",
            "node_count": len(course_structure['nodes']),
            "connection_count": len(course_structure['connections'])
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse course: {str(e)}")

# Template endpoints
@app.get("/api/templates", response_model=List[TemplateResponse])
async def list_templates():
    """List all available templates."""
    return list(templates_storage.values())

@app.get("/api/templates/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str):
    """Get details for a specific template."""
    if template_id not in templates_storage:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    
    return templates_storage[template_id]

@app.post("/api/templates/{template_id}/apply/{course_id}")
async def apply_template_to_course(template_id: str, course_id: str):
    """
    Apply a template to a course (create course from template).
    """
    if template_id not in templates_storage:
        raise HTTPException(status_code=404, detail=f"Template not found: {template_id}")
    
    if course_id in courses_storage:
        raise HTTPException(status_code=400, detail=f"Course with ID '{course_id}' already exists")
    
    template = templates_storage[template_id]
    
    # Create course from template
    course_data = {
        'id': course_id,
        'title': f"{template['name']} Course",
        'description': f"A course based on the {template['name']} template: {template['description']}",
        'version': "1.0.0",
        'tags': [template['category'], "template-based"],
        'node_count': len(template.get('structure', [])),
        'connection_count': len(template.get('connections', [])),
        'structure': {
            'course': {
                'id': course_id,
                'title': f"{template['name']} Course",
                'description': f"A course based on the {template['name']} template: {template['description']}",
                'version': "1.0.0",
                'tags': [template['category'], "template-based"],
                'metadata': {
                    'author': 'Template System',
                    'created': '2026-03-23',
                    'estimated_time': 'Variable'
                }
            },
            'nodes': {},
            'connections': [],
            'traversal_helpers': {
                'outgoing_connections': {},
                'incoming_connections': {}
            },
            'start_node': None,
            'end_nodes': []
        }
    }
    
    # Convert template structure to course structure format
    nodes_list = template.get('structure', [])
    connections_list = template.get('connections', [])
    
    # Process nodes
    for node_data in nodes_list:
        # Import parser to properly convert node data
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).parent))
        from branching_parser import BranchingCourseParser
        
        parser = BranchingCourseParser()
        parsed_node = parser._parse_node(node_data)
        if hasattr(parsed_node, '__dict__'):
            course_data['structure']['nodes'][parsed_node.id] = parsed_node.__dict__
        else:
            course_data['structure']['nodes'][str(parsed_node)] = parsed_node
    
    # Process connections
    for conn_data in connections_list:
        import sys
        from pathlib import Path
        sys.path.append(str(Path(__file__).parent))
        from branching_parser import BranchingCourseParser
        
        parser = BranchingCourseParser()
        parsed_conn = parser._parse_connection(conn_data)
        if parsed_conn:
            course_data['structure']['connections'].append(parsed_conn.__dict__)
    
    # Update traversal helpers and start/end nodes
    # Reuse parsing logic to get proper structure
    try:
        # Create temporary YAML to parse properly
        import tempfile
        import yaml
        temp_course_data = {
            'course': course_data['structure']['course'],
            'nodes': template.get('structure', []),
            'connections': template.get('connections', [])
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(temp_course_data, f)
            temp_path = f.name
        
        parser = BranchingCourseParser()
        full_structure = parser.parse_file(temp_path)
        os.unlink(temp_path)
        
        course_data['structure'] = full_structure
        course_data['node_count'] = len(full_structure['nodes'])
        course_data['connection_count'] = len(full_structure['connections'])
        
    except Exception as e:
        # Fallback to simple structure if parsing fails
        print(f"Warning: Template application had parsing issues: {e}")
        course_data['structure']['nodes'] = {}
        course_data['structure']['connections'] = []
        course_data['structure']['traversal_helpers'] = {
            'outgoing_connections': {},
            'incoming_connections': {}
        }
        course_data['structure']['start_node'] = None
        course_data['structure']['end_nodes'] = []
    
    courses_storage[course_id] = course_data
    
    return course_data

# Import yaml at the top to avoid circular import issues
import yaml

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)