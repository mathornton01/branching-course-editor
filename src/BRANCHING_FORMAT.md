# Branching Course Format Specification

## Overview
This document defines the YAML-based format for describing branching courses. The format is designed to be human-readable, easily parsable, and extensible for various branching scenarios.

## Format Structure

A branching course is defined as a YAML document with the following structure:

```yaml
course:
  id: unique-course-identifier
  title: "Course Title"
  description: "Detailed course description"
  version: "1.0.0"
  tags: ["tag1", "tag2"]
  metadata:
    author: "Course Creator"
    created: "2026-03-23"
    estimated_time: "30 minutes"

nodes:
  - id: "start"
    type: "content"
    title: "Introduction"
    content: |
      Welcome to this branching course!
      This is where your journey begins.
    position: {x: 100, y: 100}
    
  - id: "decision-1"
    type: "decision"
    title: "Choose Your Path"
    content: "Which direction would you like to take?"
    options:
      - id: "option-a"
        label: "Path A"
        description: "Take the scenic route"
        condition: "always"
        target: "path-a-start"
      - id: "option-b"
        label: "Path B"
        description: "Take the direct route"
        condition: "always"
        target: "path-b-start"
    position: {x: 300, y: 100}
    
  - id: "path-a-start"
    type: "content"
    title: "Scenic Route Begin"
    content: "You've chosen the scenic route. Enjoy the view!"
    position: {x: 500, y: 50}
    
  - id: "path-b-start"
    type: "content"
    title: "Direct Route Begin"
    content: "You've chosen the direct route. Let's get started!"
    position: {x: 500, y: 150}

connections:
  - from: "start"
    to: "decision-1"
    type: "default"
    
  - from: "decision-1"
    to: "path-a-start"
    type: "conditional"
    condition: "option-a-selected"
    
  - from: "decision-1"
    to: "path-b-start"
    type: "conditional"
    condition: "option-b-selected"

templates:
  - id: "linear-template"
    name: "Linear Progression"
    description: "Simple sequential learning path"
    category: "basic"
    structure:
      - type: "content"
        title: "Introduction"
        content: "Welcome to the course"
      - type: "content"
        title: "Lesson 1"
        content: "First lesson content"
      - type: "assessment"
        title: "Knowledge Check"
        content: "What did you learn?"
        passing_score: 80
      - type: "content"
        title: "Conclusion"
        content: "Congratulations on completing the course"
```

## Node Types

### Content Node
Displays information to the learner:
- `id`: Unique identifier
- `type`: "content"
- `title`: Display title
- `content`: Main content (supports markdown)
- `position`: {x: number, y: number} for visual layout

### Decision Node
Presents choices to the learner:
- `id`: Unique identifier
- `type`: "decision"
- `title`: Decision prompt/question
- `content`: Additional context or instructions
- `options`: Array of choice objects
  - `id`: Option identifier
  - `label`: Button/display text
  - `description`: Tooltip/help text
  - `condition`: When this option is available ("always", or variable-based)
  - `target`: Node ID to navigate to when selected
- `position`: {x: number, y: number}

### Assessment Node
Tests learner knowledge:
- `id`: Unique identifier
- `type`: "assessment"
- `title`: Assessment title
- `content`: Questions/instructions
- `questions`: Array of question objects
  - `id`: Question identifier
  - `type`: "multiple-choice", "true-false", "short-answer", etc.
  - `prompt`: Question text
  - `options`: For multiple choice (array of option objects)
  - `correct_answer`: Expected answer
  - `points`: Point value
- `passing_score`: Minimum score to pass (percentage)
- `success_target`: Node ID to go to on success
- `failure_target`: Node ID to go to on failure
- `position`: {x: number, y: number}

### Connections
Define flow between nodes:
- `from`: Source node ID
- `to`: Target node ID
- `type`: "default" (unconditional) or "conditional"
- `condition`: Variable or rule that must be true for connection to activate
- `label`: Optional display label on connection

## Extensibility
The format is designed to be extensible:
- Custom node types can be added
- Additional metadata fields can be included
- Variable tracking can be extended
- Integration points for LMS systems can be added

## Example Usage
See `sample-course.yaml` for a complete working example.