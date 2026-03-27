#!/usr/bin/env python3
"""
Auto-fix common course structural issues:
1. Chain disconnected linear sections (n3→n4, n6→n7, etc.)
2. Remove broken choice links to nonexistent nodes
"""

import json
import glob
import os
import shutil
from pathlib import Path
import datetime

COURSES_DIR = Path(__file__).parent / "courses"
BACKUP_DIR = Path(__file__).parent / "courses_backup"

def fix_course(path, dry_run=True):
    name = os.path.basename(path)
    with open(path) as f:
        data = json.load(f)

    nodes = data.get('nodes', [])
    if not nodes:
        return name, []

    node_ids = {n.get('id') for n in nodes}
    changes = []

    # Fix 1: Remove broken choice links
    for node in nodes:
        nid = node.get('id', '?')
        valid_choices = []
        for c in node.get('choices', []):
            t = c.get('next') or c.get('target') or c.get('nextNode')
            if t and t != 'end' and t not in node_ids:
                changes.append(f"Remove broken choice in {nid} → {t}")
            else:
                valid_choices.append(c)
        if len(valid_choices) != len(node.get('choices', [])):
            node['choices'] = valid_choices

    # Fix 2: Fix broken 'next' references
    for node in nodes:
        nid = node.get('id', '?')
        nxt = node.get('next', '')
        if nxt and nxt != 'end' and nxt not in node_ids:
            changes.append(f"Remove broken next in {nid} → {nxt}")
            node['next'] = ''

    # Fix 3: Chain disconnected sections
    # Build reachability
    def get_reachable(nodes, node_ids):
        if not nodes:
            return set()
        start_id = nodes[0].get('id')
        node_map = {n.get('id'): n for n in nodes}
        reachable = set()
        queue = [start_id]
        while queue:
            cur = queue.pop()
            if cur in reachable or cur not in node_ids:
                continue
            reachable.add(cur)
            node = node_map[cur]
            nxt = node.get('next')
            if nxt and nxt != 'end':
                queue.append(nxt)
            for c in node.get('choices', []):
                t = c.get('next') or c.get('target') or c.get('nextNode')
                if t and t != 'end':
                    queue.append(t)
        return reachable

    # Iteratively connect orphan sections
    max_iterations = 20
    for _ in range(max_iterations):
        reachable = get_reachable(nodes, node_ids)
        orphans = [n for n in nodes if n.get('id') not in reachable]
        if not orphans:
            break

        # Find the last node in the reachable set (by position in nodes list)
        reachable_nodes = [n for n in nodes if n.get('id') in reachable]
        
        # Find terminal reachable nodes (no next, no choices, not end type)
        end_types = {'end', 'result', 'outcome'}
        terminals = [
            n for n in reachable_nodes
            if not n.get('next') and not n.get('choices')
            and n.get('type', '') not in end_types
        ]
        
        if not terminals:
            # Use last reachable node
            terminals = [reachable_nodes[-1]]
        
        # Connect the last terminal to first orphan
        first_orphan_id = orphans[0].get('id')
        terminal = terminals[-1]
        terminal_id = terminal.get('id', '?')
        terminal['next'] = first_orphan_id
        changes.append(f"Link {terminal_id} → {first_orphan_id} (chain disconnected section)")

    if not dry_run and changes:
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    return name, changes


def run_fixes(dry_run=True):
    files = sorted(f for f in glob.glob(str(COURSES_DIR / "*.json")) if 'catalog' not in f)
    
    if not dry_run:
        BACKUP_DIR.mkdir(exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_subdir = BACKUP_DIR / ts
        backup_subdir.mkdir()
        for f in files:
            shutil.copy(f, backup_subdir / os.path.basename(f))
        print(f"Backup created: {backup_subdir}")

    total_fixes = 0
    for path in files:
        name, changes = fix_course(path, dry_run=dry_run)
        if changes:
            total_fixes += len(changes)
            print(f"\n{'DRY' if dry_run else 'FIX'} {name}:")
            for c in changes:
                print(f"  + {c}")

    print(f"\n{'Would apply' if dry_run else 'Applied'} {total_fixes} fixes across {len(files)} courses")


if __name__ == '__main__':
    import sys
    dry_run = '--apply' not in sys.argv
    if dry_run:
        print("DRY RUN — use --apply to write changes\n")
    run_fixes(dry_run=dry_run)
