#!/usr/bin/env bash
# Regenerate PASTE-THIS.txt from run-all.sh.
#
# Run this after ANY edit to run-all.sh, then re-run `python -m pytest` —
# the suite asserts the two agree.
#
# Format notes (both learned the hard way):
#
#   * The base64 goes in a QUOTED heredoc, wrapped at 76 columns, rather than
#     one long `echo <blob>` line. A single 20KB line gets truncated or
#     mangled by terminal paste handling, and an unquoted echo is also
#     subject to word splitting. Many short lines paste reliably.
#
#   * The payload is checked with sha256 after decoding. Without that, a
#     partial paste surfaces as "gunzip: invalid compressed data" with no
#     hint about what to do next.
set -euo pipefail
cd "$(dirname "$0")"

# Editors on Windows can leave CRLF behind. A CRLF script dies in CloudShell
# with "$'\r': command not found", and the line endings would be baked into
# the base64 payload, so normalise before encoding.
if grep -q $'\r' run-all.sh; then
  echo "normalising CRLF -> LF in run-all.sh"
  tr -d '\r' < run-all.sh > run-all.sh.tmp && mv run-all.sh.tmp run-all.sh
fi

# Re-inline system_prompt.txt and harness-tests.json from project/starter,
# so the CloudShell run can never deploy a stale prompt.
python3 sync-inline.py

HASH="$(sha256sum run-all.sh | cut -d' ' -f1)"

{
  echo "cat > /tmp/ra.b64 <<'B64_EOF'"
  gzip -9c run-all.sh | base64 -w 76
  echo "B64_EOF"
  echo "base64 -d /tmp/ra.b64 2>/dev/null | gunzip > run-all.sh 2>/dev/null; \\"
  echo "if [ \"\$(sha256sum run-all.sh 2>/dev/null | cut -d' ' -f1)\" = \"$HASH\" ]; then \\"
  echo "  echo 'integrity OK'; bash run-all.sh; \\"
  echo "else \\"
  echo "  echo 'PASTE INCOMPLETE OR CORRUPTED.'; \\"
  echo "  echo 'Use CloudShell Actions > Upload file to upload run-all.sh instead,'; \\"
  echo "  echo 'then run:  bash run-all.sh'; \\"
  echo "fi"
} > PASTE-THIS.txt

echo "PASTE-THIS.txt regenerated"
echo "  $(wc -c < PASTE-THIS.txt) bytes, $(wc -l < PASTE-THIS.txt) lines"
echo "  sha256 $HASH"
