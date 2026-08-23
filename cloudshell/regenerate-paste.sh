#!/usr/bin/env bash
# Regenerate the CloudShell paste files from their scripts.
#
#     bash cloudshell/regenerate-paste.sh
#
# Run this after editing any of the scripts below, then `python -m pytest` —
# the suite asserts each paste matches its script.
#
# Format notes, all learned the hard way:
#
#   * The base64 goes in a QUOTED heredoc wrapped at 76 columns, not one long
#     `echo <blob>` line. A single 20KB line gets truncated by terminal paste,
#     and an unquoted echo is also exposed to word splitting.
#
#   * Each paste verifies a sha256 after decoding. Without it a partial paste
#     surfaces as "gunzip: invalid compressed data" with no hint what to do.
#
#   * CR stripping uses tr's octal escape, \015, and never a literal
#     backslash-r. A generator once ate the backslash and left `tr -d` with a
#     bare newline, which stripped every line break out of run-all.sh and
#     committed the result. If you change these lines, edit this file
#     directly rather than patching it from another script.
set -euo pipefail
cd "$(dirname "$0")"

# make_paste <script> <paste-file>
make_paste() {
  local script="$1" out="$2"

  if LC_ALL=C grep -q "$(printf '\015')" "$script"; then
    echo "  normalising CRLF -> LF in $script"
    tr -d '\015' < "$script" > "$script.tmp" && mv "$script.tmp" "$script"
  fi

  # A script with no line breaks is the signature of the bug above. Refuse to
  # encode it rather than shipping a one-line paste that cannot work.
  local n
  n="$(wc -l < "$script")"
  if [ "$n" -lt 10 ]; then
    echo "  ERROR: $script has only $n line(s) - refusing to encode it" >&2
    return 1
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

  echo "  $out  ($(wc -c < "$out") bytes, $(wc -l < "$out") lines, from $n lines)"
  echo "    sha256 $hash"
}

# Re-inline system_prompt.txt and the rest from project/starter, so a
# CloudShell run can never deploy a stale prompt.
python3 sync-inline.py

echo "Regenerated:"
make_paste run-all.sh              PASTE-THIS.txt
make_paste create-evidence-user.sh PASTE-CREATE-USER.txt
