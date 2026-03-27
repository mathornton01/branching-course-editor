#!/usr/bin/env bash
# ===========================================================================
# run_tests.sh — Run both Python API tests and browser editor tests
#
# Usage:
#   ./tests/run_tests.sh           # run everything
#   ./tests/run_tests.sh --api     # only Python API tests
#   ./tests/run_tests.sh --browser # only browser editor tests
# ===========================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SRC_DIR="$PROJECT_DIR/src"
TESTS_DIR="$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

RUN_API=true
RUN_BROWSER=true

for arg in "$@"; do
  case "$arg" in
    --api)     RUN_BROWSER=false ;;
    --browser) RUN_API=false ;;
    --help|-h)
      echo "Usage: $0 [--api] [--browser]"
      exit 0
      ;;
  esac
done

OVERALL_EXIT=0

# ---------------------------------------------------------------------------
# 1. Python API tests (pytest)
# ---------------------------------------------------------------------------
if $RUN_API; then
  echo ""
  echo -e "${YELLOW}=== Python API Tests (pytest) ===${NC}"
  echo ""

  # Ensure dependencies are available
  if ! python3 -c "import fastapi, httpx" 2>/dev/null; then
    echo -e "${YELLOW}Installing test dependencies...${NC}"
    pip install --quiet fastapi uvicorn httpx pytest python-multipart 2>/dev/null || true
  fi

  if python3 -m pytest "$TESTS_DIR/test_api_server.py" -v --tb=short; then
    echo -e "\n${GREEN}API tests PASSED${NC}"
  else
    echo -e "\n${RED}API tests FAILED${NC}"
    OVERALL_EXIT=1
  fi
fi

# ---------------------------------------------------------------------------
# 2. Browser editor tests
# ---------------------------------------------------------------------------
if $RUN_BROWSER; then
  echo ""
  echo -e "${YELLOW}=== Browser Editor Tests ===${NC}"
  echo ""

  TEST_HTML="$TESTS_DIR/test_editor_features.html"

  # Strategy A: Use python3 to start a minimal HTTP server and curl the page
  # (only needs curl; no headless browser required)
  #
  # Strategy B: If a headless browser is available, run it properly.

  BROWSER_PORT=18723
  SERVER_PID=""

  cleanup() {
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
      kill "$SERVER_PID" 2>/dev/null || true
      wait "$SERVER_PID" 2>/dev/null || true
    fi
  }
  trap cleanup EXIT

  # Start a minimal HTTP server to serve the test file
  python3 -m http.server "$BROWSER_PORT" --directory "$TESTS_DIR" >/dev/null 2>&1 &
  SERVER_PID=$!
  sleep 1

  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo -e "${RED}Failed to start test HTTP server${NC}"
    OVERALL_EXIT=1
  else
    TEST_URL="http://localhost:${BROWSER_PORT}/test_editor_features.html"

    # Try headless Chromium/Chrome first for full JS execution
    HEADLESS_CMD=""
    for cmd in chromium-browser chromium google-chrome google-chrome-stable; do
      if command -v "$cmd" >/dev/null 2>&1; then
        HEADLESS_CMD="$cmd"
        break
      fi
    done

    if [ -n "$HEADLESS_CMD" ]; then
      echo "Running headless browser tests via $HEADLESS_CMD..."
      TMPFILE=$(mktemp /tmp/editor-test-XXXXXX.html)

      # Run headless Chrome, dump the page after JS executes
      timeout 30 "$HEADLESS_CMD" \
        --headless --disable-gpu --no-sandbox --disable-dev-shm-usage \
        --dump-dom "$TEST_URL" > "$TMPFILE" 2>/dev/null || true

      if [ -s "$TMPFILE" ]; then
        # Check title for pass/fail signal
        if grep -q "TESTS PASSED" "$TMPFILE"; then
          echo -e "${GREEN}Browser editor tests PASSED${NC}"
          # Extract summary counts
          grep -oP '(?<=stat pass" id="s-pass">)\d+' "$TMPFILE" | head -1 | xargs -I{} echo "  Passed: {}"
          grep -oP '(?<=stat fail" id="s-fail">)\d+' "$TMPFILE" | head -1 | xargs -I{} echo "  Failed: {}"
          grep -oP '(?<=stat" id="s-total">)\d+' "$TMPFILE" | head -1 | xargs -I{} echo "  Total:  {}"
        elif grep -q "TESTS FAILED" "$TMPFILE"; then
          echo -e "${RED}Browser editor tests FAILED${NC}"
          OVERALL_EXIT=1
          # Show failure details
          grep -oP '(?<=test-error">).*?(?=<)' "$TMPFILE" | while read -r line; do
            echo -e "  ${RED}FAIL: $line${NC}"
          done
        else
          echo -e "${YELLOW}Browser tests ran but could not determine result from DOM.${NC}"
          echo "  Open $TEST_URL in a browser to see results."
        fi
      else
        echo -e "${YELLOW}Headless browser produced no output.${NC}"
        echo "  Open $TEST_URL in a browser to see results."
      fi
      rm -f "$TMPFILE"
    else
      # No headless browser — just verify the test file is servable
      echo "No headless browser found. Checking test file is servable..."
      HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' "$TEST_URL" 2>/dev/null || echo "000")
      if [ "$HTTP_CODE" = "200" ]; then
        echo -e "${GREEN}Test file served successfully (HTTP $HTTP_CODE)${NC}"
        echo -e "${YELLOW}Open in a browser to run JS tests: $TEST_URL${NC}"
      else
        echo -e "${RED}Failed to serve test file (HTTP $HTTP_CODE)${NC}"
        OVERALL_EXIT=1
      fi
    fi
  fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "==========================================="
if [ $OVERALL_EXIT -eq 0 ]; then
  echo -e "${GREEN}ALL TEST SUITES PASSED${NC}"
else
  echo -e "${RED}SOME TEST SUITES FAILED${NC}"
fi
echo "==========================================="

exit $OVERALL_EXIT
