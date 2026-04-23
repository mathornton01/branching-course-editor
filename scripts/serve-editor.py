#!/usr/bin/env python3
"""
Simple static file server for serving the branching course editor
"""

import http.server
import socketserver
import os
from pathlib import Path

# Change to the src directory where our editor files are
web_dir = Path(__file__).parent / "src"
os.chdir(web_dir)

PORT = 8080

Handler = http.server.SimpleHTTPRequestHandler
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving editor at http://localhost:{PORT}")
    print(f"Open http://localhost:{PORT}/course-editor-enhanced.html to test the editor")
    print("Press Ctrl+C to stop the server")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")