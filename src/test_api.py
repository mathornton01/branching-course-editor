#!/usr/bin/env python3
"""
Test script for the Branching Courses API.
"""

import requests
import json

BASE_URL = "http://localhost:8001"

def test_api():
    """Test the API endpoints."""
    print("Testing Branching Courses API")
    print("=" * 40)
    
    # Test health endpoint
    print("1. Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/api/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    # Test list courses
    print("\n2. Testing list courses...")
    response = requests.get(f"{BASE_URL}/api/courses")
    print(f"   Status: {response.status_code}")
    courses = response.json()
    print(f"   Found {len(courses)} courses")
    for course in courses:
        print(f"   - {course['id']}: {course['title']} ({course['node_count']} nodes)")
    
    # Test get specific course
    print("\n3. Testing get specific course...")
    if courses:
        course_id = courses[0]['id']
        response = requests.get(f"{BASE_URL}/api/courses/{course_id}")
        print(f"   Status: {response.status_code}")
        course_detail = response.json()
        print(f"   Course: {course_detail['title']}")
        print(f"   Description: {course_detail['description'][:50]}...")
        print(f"   Nodes: {course_detail['node_count']}, Connections: {course_detail['connection_count']}")
    
    # Test create course
    print("\n4. Testing create course...")
    new_course = {
        "id": "test-course-001",
        "title": "Test Course via API",
        "description": "A test course created through the API",
        "version": "1.0.0",
        "tags": ["test", "api"]
    }
    response = requests.post(f"{BASE_URL}/api/courses", json=new_course)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        created_course = response.json()
        print(f"   Created: {created_course['title']}")
    else:
        print(f"   Error: {response.json()}")
    
    # Test list courses again to see the new one
    print("\n5. Testing list courses after creation...")
    response = requests.get(f"{BASE_URL}/api/courses")
    print(f"   Status: {response.status_code}")
    courses = response.json()
    print(f"   Found {len(courses)} courses")
    for course in courses:
        print(f"   - {course['id']}: {course['title']}")
    
    # Test delete course
    print("\n6. Testing delete course...")
    response = requests.delete(f"{BASE_URL}/api/courses/test-course-001")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   Response: {response.json()}")
    else:
        print(f"   Error: {response.json()}")
    
    # Test list courses after deletion
    print("\n7. Testing list courses after deletion...")
    response = requests.get(f"{BASE_URL}/api/courses")
    print(f"   Status: {response.status_code}")
    courses = response.json()
    print(f"   Found {len(courses)} courses")
    for course in courses:
        print(f"   - {course['id']}: {course['title']}")
    
    print("\n" + "=" * 40)
    print("API testing completed!")

if __name__ == "__main__":
    test_api()