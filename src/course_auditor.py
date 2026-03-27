#!/usr/bin/env python3
"""
Course Auditor Agent — scans all course JSON files for structural and content issues,
generates an audit report, and optionally auto-fixes simple problems.
"""

import json
import os
import glob
import sys
import time
import datetime
import argparse
from pathlib import Path

COURSES_DIR = Path(__file__).parent / "courses"
AUDIT_LOG = Path(__file__).parent / "audit.log"

def load_course(path):
    with open(path) as f:
        return json.load(f)

def audit_course(path):
    name = os.path.basename(path)
    issues = []
    fixes = []

    try:
        data = load_course(path)
    except json.JSONDecodeError as e:
        return name, [f"INVALID JSON: {e}"], []

    title = data.get('title', '')
    nodes = data.get('nodes', [])

    if not title:
        issues.append("ERROR: no title")
    if not nodes:
        issues.append("ERROR: no nodes")
        return name, issues, fixes

    node_map = {n.get('id'): n for n in nodes}
    node_ids = set(node_map.keys())

    # Build reachability (follow both 'next' and 'choices')
    start_id = nodes[0].get('id')
    reachable = set()
    queue = [start_id] if start_id else []
    while queue:
        cur = queue.pop()
        if cur in reachable or cur not in node_ids:
            continue
        reachable.add(cur)
        node = node_map[cur]
        # Follow next
        nxt = node.get('next')
        if nxt and nxt != 'end' and nxt not in reachable:
            queue.append(nxt)
        # Follow choices
        for c in node.get('choices', []):
            t = c.get('next') or c.get('target') or c.get('nextNode')
            if t and t != 'end' and t not in reachable:
                queue.append(t)

    orphans = node_ids - reachable - {None}

    # Check broken links
    for node in nodes:
        nid = node.get('id', '?')
        nxt = node.get('next')
        if nxt and nxt != 'end' and nxt not in node_ids:
            issues.append(f"ERROR: node {nid} next→{nxt} (missing)")
        for c in node.get('choices', []):
            t = c.get('next') or c.get('target') or c.get('nextNode')
            if t and t != 'end' and t not in node_ids:
                issues.append(f"ERROR: node {nid} choice→{t} (missing)")

    # Check empty content
    for node in nodes:
        nid = node.get('id', '?')
        ntype = node.get('type', 'text')
        content = node.get('content', '')
        if ntype in ('text', 'content', 'scenario', 'question', 'decision') and not content:
            issues.append(f"WARN: node {nid} ({ntype}) empty content")

    # Check dead-end nodes (no next, no choices, not a leaf type)
    leaf_types = {'end', 'result', 'outcome', 'assessment', 'quiz'}
    for node in nodes:
        nid = node.get('id', '?')
        ntype = node.get('type', 'text')
        nxt = node.get('next')
        choices = node.get('choices', [])
        if not nxt and not choices and ntype not in leaf_types and nid != nodes[-1].get('id'):
            issues.append(f"WARN: node {nid} ({ntype}) dead end (no next, no choices)")

    # Report orphans
    if orphans:
        issues.append(f"WARN: {len(orphans)} unreachable nodes: {sorted(orphans)[:5]}{'...' if len(orphans)>5 else ''}")

    return name, issues, fixes

def run_audit(fix=False, verbose=False):
    files = sorted(f for f in glob.glob(str(COURSES_DIR / "*.json")) if 'catalog' not in f)
    
    total = len(files)
    clean = 0
    error_count = 0
    warn_count = 0
    
    timestamp = datetime.datetime.now().isoformat(timespec='seconds')
    lines = [f"\n{'='*60}", f"COURSE AUDIT — {timestamp}", f"{'='*60}"]
    
    for path in files:
        name, issues, fixes = audit_course(path)
        errors = [i for i in issues if i.startswith('ERROR')]
        warns = [i for i in issues if i.startswith('WARN')]
        
        if not issues:
            clean += 1
            if verbose:
                lines.append(f"  OK  {name}")
        else:
            error_count += len(errors)
            warn_count += len(warns)
            status = "ERR " if errors else "WARN"
            lines.append(f"  {status} {name}")
            for issue in issues:
                lines.append(f"       {issue}")
    
    lines.append(f"\nSUMMARY: {total} courses | {clean} clean | {error_count} errors | {warn_count} warnings")
    
    report = "\n".join(lines)
    
    # Write to log
    with open(AUDIT_LOG, 'a') as f:
        f.write(report + "\n")
    
    print(report)
    return error_count, warn_count

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Course auditor')
    parser.add_argument('--fix', action='store_true', help='Auto-fix simple issues')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show clean courses too')
    parser.add_argument('--watch', '-w', metavar='MINUTES', type=int, help='Watch mode: re-audit every N minutes')
    args = parser.parse_args()
    
    run_audit(fix=args.fix, verbose=args.verbose)
    
    if args.watch:
        interval = args.watch * 60
        print(f"\nWatching — next audit in {args.watch} minutes...")
        while True:
            time.sleep(interval)
            run_audit(fix=args.fix, verbose=args.verbose)
            print(f"\nNext audit in {args.watch} minutes...")
