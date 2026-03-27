# Branching Course Format Specification

## Overview
This document defines the YAML-based format for describing branching courses. The format supports every major branching pattern used in interactive learning, adventure books, and simulation scenarios — including deterministic, probabilistic, conditional, and gated flows.

---

## Top-Level Structure

```yaml
course:
  id: unique-course-identifier
  title: "Course Title"
  description: "Detailed course description"
  version: "1.0.0"
  tags: ["tag1", "tag2"]
  metadata:
    author: "Course Creator"
    created: "2026-03-25"
    estimated_time: "30 minutes"

nodes:
  - ...  # see Node Types below

connections:
  - ...  # see Connections below
```

---

## Node Types

### `content` — Linear Content
Displays information. Moves unconditionally to the next node via a `default` connection.

```yaml
- id: "intro"
  type: "content"
  title: "Introduction"
  content: |
    Welcome! This is markdown-supported body text.
  position: {x: 100, y: 100}
```

---

### `decision` — User Choice Branch
Presents explicit options to the learner. The learner picks one; the runtime follows the matching connection.

```yaml
- id: "fork-1"
  type: "decision"
  title: "Which path?"
  content: "Choose your direction:"
  options:
    - id: "opt-a"
      label: "Beginner Path"
      description: "Start from basics"
    - id: "opt-b"
      label: "Advanced Path"
      description: "Jump to the deep end"
  position: {x: 300, y: 100}
```

Connections from a `decision` node carry a `label` matching one of the option labels (or left blank for the default fallback).

---

### `assessment` — Scored Test with Pass/Fail Branch
Tests learner knowledge. Routes to `success_target` or `failure_target` based on score vs `passing_score`.

```yaml
- id: "quiz-1"
  type: "assessment"
  title: "Knowledge Check"
  content: "Answer all questions."
  questions:
    - id: "q1"
      type: "multiple-choice"
      prompt: "What is 2+2?"
      options:
        - {id: "a", label: "3"}
        - {id: "b", label: "4", correct: true}
        - {id: "c", label: "5"}
      points: 10
    - id: "q2"
      type: "true-false"
      prompt: "The sky is blue."
      correct_answer: true
      points: 10
  passing_score: 80          # percentage required to pass
  success_target: "module-2" # node ID on pass
  failure_target: "review-1" # node ID on fail
  position: {x: 600, y: 100}
```

Question types: `multiple-choice`, `true-false`, `short-answer`, `numeric`.

---

### `random` — Uniform Random Branch
The runtime picks one of the outgoing connections completely at random (equal probability). Use for unpredictable narrative branches or randomized practice sets.

```yaml
- id: "random-event"
  type: "random"
  title: "Random Encounter"
  content: "Something unexpected happens..."
  position: {x: 400, y: 200}
```

Connections from a `random` node have `type: random`. The runtime selects one uniformly.

---

### `weighted` — Weighted Probability Branch
Like `random`, but each outgoing connection carries a `weight` (0–100, percentage). The runtime samples proportionally. Weights should sum to 100; if they don't the runtime normalizes them automatically.

```yaml
- id: "weighted-fork"
  type: "weighted"
  title: "Scenario Draw"
  content: "The outcome depends on probability."
  position: {x: 500, y: 200}
```

Connections from a `weighted` node **must** include a `weight` field:

```yaml
connections:
  - from: "weighted-fork"
    to:   "easy-path"
    type: "weighted"
    label: "Easy"
    weight: 70          # 70% chance

  - from: "weighted-fork"
    to:   "hard-path"
    type: "weighted"
    label: "Hard"
    weight: 30          # 30% chance
```

---

### `condition` — Variable/Expression Branch
Evaluates a runtime expression (e.g. a learner variable or score) and routes to the matching outgoing connection. Connection labels carry the matching condition strings. If no connection matches, the `default_target` is used.

```yaml
- id: "score-router"
  type: "condition"
  title: "Score Router"
  condition: "score"          # the variable or expression to evaluate
  default_target: "review-1"  # fallback node ID if nothing matches
  position: {x: 700, y: 150}
```

Connections carry the condition that must be satisfied to take that path:

```yaml
connections:
  - from: "score-router"
    to:   "advanced-module"
    type: "conditional"
    label: "score >= 90"

  - from: "score-router"
    to:   "standard-module"
    type: "conditional"
    label: "score >= 70"

  - from: "score-router"
    to:   "review-1"
    type: "conditional"
    label: "score < 70"
```

Expression operators supported by the runtime: `==`, `!=`, `<`, `<=`, `>`, `>=`, `and`, `or`, `not`. Variables are those set by prior nodes or the LMS context.

---

### `gate` — Conditional Block
Holds the learner at this node until a condition becomes true (e.g. they have completed a required module elsewhere, or enough time has passed). When the gate opens, the learner proceeds to `default_target` or the single outgoing connection.

```yaml
- id: "prereq-gate"
  type: "gate"
  title: "Prerequisite Check"
  content: "Complete Module 1 before continuing."
  condition: "completed_modules >= 1"
  default_target: "module-2-intro"
  position: {x: 800, y: 150}
```

Runtimes should periodically re-evaluate the `condition` and unlock the gate when it becomes true. A gate with no condition (or `condition: ""`) always passes immediately.

---

### `end` — Terminal Node
Marks the end of a path. No outgoing connections.

```yaml
- id: "finish"
  type: "end"
  title: "Complete"
  position: {x: 1200, y: 150}
```

---

## Connections

Every edge in the graph is a connection. The `type` field describes the branching semantics.

```yaml
connections:
  - from: "node-a"        # source node ID
    to:   "node-b"        # target node ID
    type: "default"       # see types below
    label: "optional label shown on the edge"
    condition: ""         # expression string (for conditional type)
    weight: 50            # probability weight 0-100 (for weighted type)
```

### Connection Types

| type | description |
|------|-------------|
| `default` | Unconditional. Taken automatically when the source node completes. |
| `conditional` | Taken only when `condition` evaluates true. Used with `decision` and `condition` nodes. |
| `weighted` | Sampled by probability. Used with `weighted` nodes. `weight` must be set. |
| `random` | One of these is selected uniformly at random. Used with `random` nodes. |

---

## Variable System

Nodes may read and write runtime variables. Variables persist across the learner's session and are used by `condition` and `gate` nodes.

Common built-in variables:

| variable | type | description |
|----------|------|-------------|
| `score` | number | Current accumulated score (0–100) |
| `completed_modules` | number | Count of completed content nodes |
| `attempts` | number | How many times the current node has been visited |
| `path` | string | The label of the last decision option chosen |
| `time_elapsed` | number | Seconds since course start |

Custom variables can be set by any node using a `set_variables` block:

```yaml
- id: "path-a-start"
  type: "content"
  title: "Scenic Route"
  content: "You chose the scenic path."
  set_variables:
    path: "scenic"
    visited_scenic: true
  position: {x: 500, y: 50}
```

---

## Full Branching Taxonomy

| Pattern | Node type | How it works |
|---------|-----------|-------------|
| Linear | `content` | Always proceeds forward |
| User choice | `decision` | Learner picks from explicit options |
| Scored pass/fail | `assessment` | Routes on score threshold |
| Uniform random | `random` | Runtime picks one path at equal probability |
| Weighted random | `weighted` | Runtime samples by assigned weights |
| Variable switch | `condition` | Evaluates expression, routes to matching arm |
| Conditional block | `gate` | Holds until expression becomes true |
| Terminal | `end` | No exit |

---

## Example: Mixed Branching Course

```yaml
course:
  id: "adventure-1"
  title: "The Forest Adventure"
  version: "1.0.0"

nodes:
  - {id: "start",      type: "content",    title: "Forest Edge",      content: "You stand at the forest edge.", position: {x: 80,  y: 200}}
  - {id: "fork",       type: "decision",   title: "Which way?",       content: "Left path or right path?",
     options: [{id: "left", label: "Go left"}, {id: "right", label: "Go right"}],                              position: {x: 320, y: 200}}
  - {id: "left-path",  type: "content",    title: "Left Path",        content: "A quiet trail.",                position: {x: 560, y: 100}}
  - {id: "right-path", type: "content",    title: "Right Path",       content: "A bustling road.",              position: {x: 560, y: 300}}
  - {id: "encounter",  type: "weighted",   title: "Random Encounter", content: "Something happens...",          position: {x: 800, y: 200}}
  - {id: "easy",       type: "content",    title: "Friendly Traveler",content: "You meet a friend.",            position: {x: 1040,y: 100}}
  - {id: "hard",       type: "content",    title: "Bandit Attack",    content: "You're ambushed!",              position: {x: 1040,y: 300}}
  - {id: "quiz",       type: "assessment", title: "Quick Check",      passing_score: 70,
     success_target: "win",  failure_target: "retry",                                                           position: {x: 1280,y: 200}}
  - {id: "win",        type: "end",        title: "Victory",                                                    position: {x: 1520,y: 200}}
  - {id: "retry",      type: "gate",       title: "Retry Gate",       condition: "attempts < 3",
     default_target: "quiz",                                                                                     position: {x: 1280,y: 380}}

connections:
  - {from: "start",      to: "fork",       type: "default"}
  - {from: "fork",       to: "left-path",  type: "conditional", label: "Go left"}
  - {from: "fork",       to: "right-path", type: "conditional", label: "Go right"}
  - {from: "left-path",  to: "encounter",  type: "default"}
  - {from: "right-path", to: "encounter",  type: "default"}
  - {from: "encounter",  to: "easy",       type: "weighted", label: "Friendly", weight: 70}
  - {from: "encounter",  to: "hard",       type: "weighted", label: "Bandit",   weight: 30}
  - {from: "easy",       to: "quiz",       type: "default"}
  - {from: "hard",       to: "quiz",       type: "default"}
  - {from: "quiz",       to: "win",        type: "default"}
  - {from: "retry",      to: "quiz",       type: "default"}
```
