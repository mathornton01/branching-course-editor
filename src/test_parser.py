#!/usr/bin/env python3
"""
Test script for the branching course parser.
"""

import json
from branching_parser import parse_branching_course, BranchingCourseParser


def test_parser():
    """Test the parser with sample course."""
    print("Testing Branching Course Parser")
    print("=" * 40)
    
    # Parse the sample course
    course_structure = parse_branching_course("sample-course.yaml")
    
    print(f"Course ID: {course_structure['course']['id']}")
    print(f"Course Title: {course_structure['course']['title']}")
    print(f"Number of nodes: {len(course_structure['nodes'])}")
    print(f"Number of connections: {len(course_structure['connections'])}")
    
    # Test traversal helpers
    helpers = course_structure['traversal_helpers']
    print(f"Start node: {course_structure['start_node']}")
    print(f"End nodes: {course_structure['end_nodes']}")
    
    # Test getting next nodes from start
    start_node = course_structure['start_node']
    next_nodes = helpers['outgoing_connections'].get(start_node, [])
    print(f"\nFrom start node '{start_node}':")
    for conn in next_nodes:
        print(f"  -> {conn['to_node']} (type: {conn['type']})")
    
    # Test decision node traversal
    decision_node = "learning-style-question"
    decision_outgoing = helpers['outgoing_connections'].get(decision_node, [])
    print(f"\nFrom decision node '{decision_node}':")
    for conn in decision_outgoing:
        condition = conn.get('condition', 'none')
        print(f"  -> {conn['to_node']} (if {condition})")
    
    # Test assessment node traversal
    assessment_node = "knowledge-check"
    assessment_outgoing = helpers['outgoing_connections'].get(assessment_node, [])
    print(f"\nFrom assessment node '{assessment_node}':")
    for conn in assessment_outgoing:
        condition = conn.get('condition', 'none')
        print(f"  -> {conn['to_node']} (if {condition})")
    
    # Test the traversal logic
    print("\n" + "=" * 40)
    print("Testing Traversal Logic")
    print("=" * 40)
    
    parser = BranchingCourseParser()
    
    # Test visual path selection
    visual_next = parser.get_next_nodes(
        course_structure, 
        "learning-style-question", 
        selected_option="visual-learner"
    )
    print(f"Visual learner path: {visual_next}")
    
    # Test auditory path selection
    auditory_next = parser.get_next_nodes(
        course_structure, 
        "learning-style-question", 
        selected_option="auditory-learner"
    )
    print(f"Auditory learner path: {auditory_next}")
    
    # Test kinesthetic path selection
    kinesthetic_next = parser.get_next_nodes(
        course_structure, 
        "learning-style-question", 
        selected_option="kinesthetic-learner"
    )
    print(f"Kinesthetic learner path: {kinesthetic_next}")
    
    # Test assessment traversal (passing score)
    assessment_pass_next = parser.get_next_nodes(
        course_structure, 
        "knowledge-check", 
        assessment_score=85  # Passing score
    )
    print(f"Assessment pass (85%): {assessment_pass_next}")
    
    # Test assessment traversal (failing score)
    assessment_fail_next = parser.get_next_nodes(
        course_structure, 
        "knowledge-check", 
        assessment_score=50  # Failing score
    )
    print(f"Assessment fail (50%): {assessment_fail_next}")
    
    print("\nParser test completed successfully!")


if __name__ == "__main__":
    test_parser()