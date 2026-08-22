#!/usr/bin/env bash
# Regenerate PASTE-THIS.txt from run-all.sh.
#
# Run this after ANY edit to run-all.sh, then re-run `python -m pytest` —
# the suite asserts the two agree.
set -euo pipefail
cd "$(dirname "$0")"

# Editors on Windows can leave CRLF behind. A CRLF script dies in CloudShell
# with "$'\r': command not found", and the line endings would be baked into
# the base64 payload, so normalise before encoding.
if grep -q $'\r' run-all.sh; then
  echo "normalising CRLF -> LF in run-all.sh"
  tr -d '\r' < run-all.sh > run-all.sh.tmp && mv run-all.sh.tmp run-all.sh
fi

printf 'echo %s | base64 -d | gunzip > run-all.sh && bash run-all.sh\n' \
  "$(gzip -9c run-all.sh | base64 -w0)" > PASTE-THIS.txt

echo "PASTE-THIS.txt regenerated ($(wc -c < PASTE-THIS.txt) bytes)"
