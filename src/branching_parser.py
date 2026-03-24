#!/usr/bin/env python3
"""
Branching Course Parser
Parses YAML-based branching course definitions into traversable web structures.
"""

import yaml
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class NodeType(Enum):
    CONTENT = "content"
    DECISION = "decision"
    ASSESSMENT = "assessment"


class ConnectionType(Enum):
    DEFAULT = "default"
    CONDITIONAL = "conditional"


@dataclass
class Position:
    x: int
    y: int


@dataclass
class ContentNode:
    id: str
    type: str
    title: str
    content: str
    position: Position


@dataclass
class DecisionOption:
    id: str
    label: str
    description: str
    condition: str
    target: str


@dataclass
class DecisionNode:
    id: str
    type: str
    title: str
    content: str
    options: List[DecisionOption]
    position: Position


@dataclass
class AssessmentQuestion:
    id: str
    type: str
    prompt: str
    options: List[Dict[str, str]]
    correct_answer: str
    points: int


@dataclass
class AssessmentNode:
    id: str
    type: str
    title: str
    content: str
    questions: List[AssessmentQuestion]
    passing_score: int
    success_target: str
    failure_target: str
    position: Position


@dataclass
class Connection:
    from_node: str
    to_node: str
    type: str
    condition: Optional[str] = None
    label: Optional[str] = None


@dataclass
class CourseMetadata:
    author: str
    created: str
    estimated_time: str


@dataclass
class Course:
    id: str
    title: str
    description: str
    version: str
    tags: List[str]
    metadata: CourseMetadata
    
    # Parsed content
    nodes: Dict[str, Any]  # Will contain ContentNode, DecisionNode, or AssessmentNode
    connections: List[Connection]


class BranchingCourseParser:
    """Parses branching course YAML files into traversable structures."""
    
    def __init__(self):
        self.nodes = {}
        self.connections = []
        
    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a YAML branching course file.
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            Dictionary representing the parsed course structure
        """
        with open(file_path, 'r') as file:
            data = yaml.safe_load(file)
            
        return self.parse_data(data)
    
    def parse_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse branching course data from dictionary.
        
        Args:
            data: Dictionary containing course data
            
        Returns:
            Dictionary representing the parsed course structure
        """
        # Parse course info
        course_info = data.get('course', {})
        course = Course(
            id=course_info.get('id', ''),
            title=course_info.get('title', ''),
            description=course_info.get('description', ''),
            version=course_info.get('version', '1.0.0'),
            tags=course_info.get('tags', []),
            metadata=CourseMetadata(
                author=course_info.get('metadata', {}).get('author', ''),
                created=course_info.get('metadata', {}).get('created', ''),
                estimated_time=course_info.get('metadata', {}).get('estimated_time', '')
            ),
            nodes={},
            connections=[]
        )
        
        # Parse nodes
        nodes_data = data.get('nodes', [])
        for node_data in nodes_data:
            node = self._parse_node(node_data)
            if node:
                course.nodes[node.id] = node
                
        # Parse connections
        connections_data = data.get('connections', [])
        for conn_data in connections_data:
            connection = self._parse_connection(conn_data)
            if connection:
                course.connections.append(connection)
                
        # Convert to web-traversable structure
        web_structure = self._create_web_structure(course)
        
        return web_structure
    
    def _parse_node(self, node_data: Dict[str, Any]) -> Any:
        """Parse a single node based on its type."""
        node_type = node_data.get('type', '')
        position_data = node_data.get('position', {'x': 0, 'y': 0})
        position = Position(x=position_data.get('x', 0), y=position_data.get('y', 0))
        
        if node_type == NodeType.CONTENT.value:
            return ContentNode(
                id=node_data.get('id', ''),
                type=node_type,
                title=node_data.get('title', ''),
                content=node_data.get('content', ''),
                position=position
            )
            
        elif node_type == NodeType.DECISION.value:
            options_data = node_data.get('options', [])
            options = []
            for opt_data in options_data:
                option = DecisionOption(
                    id=opt_data.get('id', ''),
                    label=opt_data.get('label', ''),
                    description=opt_data.get('description', ''),
                    condition=opt_data.get('condition', 'always'),
                    target=opt_data.get('target', '')
                )
                options.append(option)
                
            return DecisionNode(
                id=node_data.get('id', ''),
                type=node_type,
                title=node_data.get('title', ''),
                content=node_data.get('content', ''),
                options=options,
                position=position
            )
            
        elif node_type == NodeType.ASSESSMENT.value:
            questions_data = node_data.get('questions', [])
            questions = []
            for q_data in questions_data:
                question = AssessmentQuestion(
                    id=q_data.get('id', ''),
                    type=q_data.get('type', 'multiple-choice'),
                    prompt=q_data.get('prompt', ''),
                    options=q_data.get('options', []),
                    correct_answer=q_data.get('correct_answer', ''),
                    points=q_data.get('points', 0)
                )
                questions.append(question)
                
            return AssessmentNode(
                id=node_data.get('id', ''),
                type=node_type,
                title=node_data.get('title', ''),
                content=node_data.get('content', ''),
                questions=questions,
                passing_score=node_data.get('passing_score', 70),
                success_target=node_data.get('success_target', ''),
                failure_target=node_data.get('failure_target', ''),
                position=position
            )
            
        else:
            # Unknown node type - treat as content for safety
            return ContentNode(
                id=node_data.get('id', 'unknown'),
                type=node_type,
                title=node_data.get('title', 'Unknown Node'),
                content=node_data.get('content', ''),
                position=position
            )
    
    def _parse_connection(self, conn_data: Dict[str, Any]) -> Optional[Connection]:
        """Parse a connection between nodes."""
        from_node = conn_data.get('from')
        to_node = conn_data.get('to')
        conn_type = conn_data.get('type', 'default')
        
        if not from_node or not to_node:
            return None
            
        return Connection(
            from_node=from_node,
            to_node=to_node,
            type=conn_type,
            condition=conn_data.get('condition'),
            label=conn_data.get('label')
        )
    
    def _create_web_structure(self, course: Course) -> Dict[str, Any]:
        """
        Convert parsed course into a web-traversable structure.
        
        Returns:
            Dictionary suitable for consumption by frontend applications
        """
        # Convert nodes to serializable format
        nodes_dict = {}
        for node_id, node in course.nodes.items():
            if hasattr(node, '__dict__'):
                nodes_dict[node_id] = asdict(node)
            else:
                nodes_dict[node_id] = node
                
        # Convert connections to serializable format
        connections_list = [asdict(conn) for conn in course.connections]
        
        # Create traversal helpers
        traversal_helpers = self._create_traversal_helpers(course)
        
        web_structure = {
            'course': {
                'id': course.id,
                'title': course.title,
                'description': course.description,
                'version': course.version,
                'tags': course.tags,
                'metadata': asdict(course.metadata)
            },
            'nodes': nodes_dict,
            'connections': connections_list,
            'traversal_helpers': traversal_helpers,
            'start_node': self._find_start_node(course),
            'end_nodes': self._find_end_nodes(course)
        }
        
        return web_structure
    
    def _create_traversal_helpers(self, course: Course) -> Dict[str, Any]:
        """Create helper structures for easy traversal."""
        # Map of node ID to outgoing connections
        outgoing_map = {}
        # Map of node ID to incoming connections
        incoming_map = {}
        
        for conn in course.connections:
            # Outgoing connections
            if conn.from_node not in outgoing_map:
                outgoing_map[conn.from_node] = []
            outgoing_map[conn.from_node].append(asdict(conn))
            
            # Incoming connections
            if conn.to_node not in incoming_map:
                incoming_map[conn.to_node] = []
            incoming_map[conn.to_node].append(asdict(conn))
            
        return {
            'outgoing_connections': outgoing_map,
            'incoming_connections': incoming_map
        }
    
    def _find_start_node(self, course: Course) -> Optional[str]:
        """Find the starting node (node with no incoming connections)."""
        incoming_nodes = set()
        for conn in course.connections:
            incoming_nodes.add(conn.to_node)
            
        for node_id in course.nodes.keys():
            if node_id not in incoming_nodes:
                return node_id
                
        return None
    
    def _find_end_nodes(self, course: Course) -> List[str]:
        """Find end nodes (nodes with no outgoing connections)."""
        outgoing_nodes = set()
        for conn in course.connections:
            outgoing_nodes.add(conn.from_node)
            
        end_nodes = []
        for node_id in course.nodes.keys():
            if node_id not in outgoing_nodes:
                end_nodes.append(node_id)
                
        return end_nodes
    
    def get_next_nodes(self, course_structure: Dict[str, Any], current_node_id: str, 
                      selected_option: str = None, assessment_score: int = None) -> List[str]:
        """
        Get possible next nodes from current node based on choices.
        
        Args:
            course_structure: Parsed course structure
            current_node_id: ID of current node
            selected_option: For decision nodes, which option was selected
            assessment_score: For assessment nodes, the score achieved
            
        Returns:
            List of node IDs that can be traversed to next
        """
        connections = course_structure.get('traversal_helpers', {}).get('outgoing_connections', {}).get(current_node_id, [])
        next_nodes = []
        
        for conn in connections:
            # Check if connection is traversable based on conditions
            if self._is_traversable(conn, course_structure, selected_option, assessment_score):
                next_nodes.append(conn['to_node'])
                
        return next_nodes
    
    def _is_traversable(self, connection: Dict[str, Any], course_structure: Dict[str, Any],
                       selected_option: str = None, assessment_score: int = None) -> bool:
        """Check if a connection can be traversed based on its conditions."""
        conn_type = connection.get('type', 'default')
        condition = connection.get('condition')
        
        # Default connections are always traversable
        if conn_type == 'default':
            return True
            
        # Conditional connections need condition evaluation
        if condition == 'always':
            return True
        elif condition == 'assessment-passed':
            return assessment_score is not None and assessment_score >= 70  # Assuming 70% passing
        elif condition == 'assessment-failed':
            return assessment_score is not None and assessment_score < 70
        elif condition.endswith('-selected'):
            # Option selection condition (e.g., "visual-learner-selected")
            option_id = condition.replace('-selected', '')
            return selected_option == option_id
        elif condition.startswith('score>='):
            # Score-based condition (e.g., "score>=80")
            try:
                threshold = int(condition.split('>=')[1])
                return assessment_score is not None and assessment_score >= threshold
            except (ValueError, IndexError):
                return False
                
        # For unknown conditions, default to False for safety
        return False


def parse_branching_course(file_path: str) -> Dict[str, Any]:
    """
    Convenience function to parse a branching course file.
    
    Args:
        file_path: Path to the YAML file
        
    Returns:
        Parsed course structure as dictionary
    """
    parser = BranchingCourseParser()
    return parser.parse_file(file_path)


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "sample-course.yaml"
        
    try:
        course_structure = parse_branching_course(file_path)
        print(json.dumps(course_structure, indent=2, default=str))
    except Exception as e:
        print(f"Error parsing course: {e}")
        sys.exit(1)