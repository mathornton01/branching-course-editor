#!/bin/bash
# Watchdog: restart course generator if it's not running
LOG=/home/mathornton/micah/herald-workspaces/simon/branching_courses_project/src/generator.log
SRC=/home/mathornton/micah/herald-workspaces/simon/branching_courses_project/src

if ! pgrep -f "course_generator.py" > /dev/null; then
    echo "[$(date '+%H:%M:%S')] Watchdog: generator not running, restarting..." >> "$LOG"
    cd "$SRC" && nohup python3 course_generator.py >> "$LOG" 2>&1 &
    echo "[$(date '+%H:%M:%S')] Watchdog: restarted with PID $!" >> "$LOG"
else
    echo "[$(date '+%H:%M:%S')] Watchdog: generator OK (PID $(pgrep -f course_generator.py))" >> "$LOG"
fi

ILOG=/home/mathornton/micah/herald-workspaces/simon/branching_courses_project/src/improver.log
if ! pgrep -f "course_improver.py" > /dev/null; then
    echo "[$(date '+%H:%M:%S')] Watchdog: improver not running, restarting..." >> "$ILOG"
    cd "$SRC" && nohup python3 course_improver.py >> "$ILOG" 2>&1 &
    echo "[$(date '+%H:%M:%S')] Watchdog: improver restarted with PID $!" >> "$ILOG"
else
    echo "[$(date '+%H:%M:%S')] Watchdog: improver OK (PID $(pgrep -f course_improver.py))" >> "$ILOG"
fi

WLOG=/home/mathornton/micah/herald-workspaces/simon/branching_courses_project/src/api_server.log
if ! pgrep -f "uvicorn course_api_server" > /dev/null; then
    echo "[$(date '+%H:%M:%S')] Watchdog: web server not running, restarting..." >> "$WLOG"
    cd "$SRC" && nohup python3 -m uvicorn course_api_server:app --host 0.0.0.0 --port 8080 >> "$WLOG" 2>&1 &
    echo "[$(date '+%H:%M:%S')] Watchdog: web server restarted with PID $!" >> "$WLOG"
fi
