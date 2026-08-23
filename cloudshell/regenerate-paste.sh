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

make_paste() {           # make_paste <script> <paste-file>
  local script="$1" out="$2"
  if grep -q $'
' "$script"; then
    tr -d '
' < "$script" > "$script.tmp" && mv "$script.tmp" "$script"
  fi
  local hash
  hash="$(sha256sum "$script" | cut -d' ' -f1)"
  {
    echo "cat > /tmp/ra.b64 <<'B64_EOF'"
    gzip -9c "$script" | base64 -w 76
    echo "B64_EOF"
    echo "base64 -d /tmp/ra.b64 2>/dev/null | gunzip > $script 2>/dev/null; \\"
    echo "if [ \"\$(sha256sum $script 2>/dev/null | cut -d' ' -f1)\" = \"$hash\" ]; then \\"
    echo "  echo 'integrity OK'; bash $script; \\"
    echo "else \\"
    echo "  echo 'PASTE INCOMPLETE OR CORRUPTED.'; \\"
    echo "  echo 'Use CloudShell Actions > Upload file to upload $script instead,'; \\"
    echo "  echo 'then run:  bash $script'; \\"
    echo "fi"
  } > "$out"
  echo "  $out  ($(wc -c < "$out") bytes, $(wc -l < "$out") lines)"
  echo "    sha256 $hash"
}

echo "Regenerated:"
make_paste run-all.sh            PASTE-THIS.txt
make_paste create-evidence-user.sh PASTE-CREATE-USER.txt
make_paste create-flow.sh          PASTE-CREATE-FLOW.txt
