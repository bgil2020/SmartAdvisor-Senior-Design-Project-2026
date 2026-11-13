#!/usr/bin/env bash
set -euo pipefail

Xvfb "${DISPLAY}" -screen 0 1280x720x24 -nolisten tcp -noreset &
xvfb_pid=$!
cleanup() {
  kill "${app_pid:-}" 2>/dev/null || true
  kill "${xvfb_pid}" 2>/dev/null || true
  wait "${app_pid:-}" 2>/dev/null || true
  wait "${xvfb_pid}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if [[ "${RENDER_STARTUP_BROWSER_SMOKE:-false}" == "true" ]]; then
  if [[ "${SYLLABUS_ACQUISITION_ENABLED:-false}" != "false" || "${CONVERSATIONAL_PARSER_MODE:-deterministic}" != "deterministic" ]]; then
    echo '{"status":"failed","reason":"startup_smoke_requires_acquisition_and_gemini_disabled"}'
    exit 2
  fi
  python /app/scripts/verify_headed_runtime.py
fi

"$@" &
app_pid=$!
wait "${app_pid}"
