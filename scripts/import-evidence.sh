#!/usr/bin/env bash
# =============================================================================
#  Import a CloudShell evidence bundle into this repo and push it.
#
#      bash scripts/import-evidence.sh [evidence.tar.gz] [screenshots-dir]
#
#  With no arguments it looks for the newest evidence.tar.gz in ~/Downloads.
#
#  Run this on YOUR machine, not in CloudShell — git and gh are already
#  authenticated here, so no GitHub token is needed anywhere.
#
#  What it does:
#    1. Extracts the bundle into evidence/run-NN/
#    2. Copies any screenshots you point it at
#    3. Force-adds the artefacts .gitignore normally excludes (the eval
#       dataset is generated output, but it IS submission evidence)
#    4. Writes an INDEX.md describing what each file proves
#    5. Commits and pushes
# =============================================================================

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

C_OK=$'\033[0;32m'; C_WARN=$'\033[0;33m'; C_ERR=$'\033[0;31m'
C_HEAD=$'\033[1;36m'; C_OFF=$'\033[0m'
ok()   { printf '  %s✓%s %s\n' "$C_OK" "$C_OFF" "$*"; }
warn() { printf '  %s!%s %s\n' "$C_WARN" "$C_OFF" "$*"; }
step() { printf '\n%s━━━ %s%s\n' "$C_HEAD" "$*" "$C_OFF"; }
die()  { printf '\n%s✗ %s%s\n' "$C_ERR" "$*" "$C_OFF" >&2; exit 1; }

BUNDLE="${1:-}"
SHOTS="${2:-}"

# ---------------------------------------------------------------- locate ----
step "Locating the bundle"

if [ -z "$BUNDLE" ]; then
  # Browsers and upload tools both rename files - a Claude upload arrives as
  # "<hash>-evidence.tar.gz", Chrome adds " (1)" - so match anything with
  # "evidence" in the name and take the newest.
  for dir in "$HOME/Downloads" "$USERPROFILE/Downloads" \
             "/c/Users/$USER/Downloads" "$HOME/Desktop" \
             "$HOME/.claude/uploads" "$(pwd)"; do
    [ -d "$dir" ] || continue
    found="$(find "$dir" -maxdepth 3 -iname '*evidence*.tar.gz' -newermt "-14 days" -printf '%T@ %p\n' 2>/dev/null \
             | sort -rn | head -1 | cut -d" " -f2-)"
    if [ -n "$found" ]; then BUNDLE="$found"; break; fi
  done
fi

[ -n "$BUNDLE" ] || die "No evidence.tar.gz found.
     Download it from CloudShell (Actions > Download file), then either
     move it to your Downloads folder or pass the path:
       bash scripts/import-evidence.sh /path/to/evidence.tar.gz"
[ -f "$BUNDLE" ] || die "Not a file: $BUNDLE"

ok "$BUNDLE ($(du -h "$BUNDLE" | cut -f1))"

# ----------------------------------------------------------------- slot -----
step "Choosing a run folder"

RUN_N=1
while [ -d "evidence/run-$(printf '%02d' "$RUN_N")" ]; do
  RUN_N=$((RUN_N + 1))
done
RUN_DIR="evidence/run-$(printf '%02d' "$RUN_N")"
mkdir -p "$RUN_DIR"
ok "$RUN_DIR"

# --------------------------------------------------------------- extract ----
step "Extracting"

TMP="$(mktemp -d)"
tar -xzf "$BUNDLE" -C "$TMP"
# The bundle contains a top-level evidence/ directory.
SRC="$TMP/evidence"
[ -d "$SRC" ] || SRC="$TMP"

cp -r "$SRC"/. "$RUN_DIR"/
rm -rf "$TMP"
ok "$(find "$RUN_DIR" -type f | wc -l) files"

# ----------------------------------------------------------- screenshots ----
step "Screenshots"

mkdir -p "$RUN_DIR/screenshots"
if [ -n "$SHOTS" ] && [ -d "$SHOTS" ]; then
  n=0
  for ext in png jpg jpeg gif webp; do
    for f in "$SHOTS"/*."$ext" "$SHOTS"/*."${ext^^}"; do
      [ -f "$f" ] || continue
      cp "$f" "$RUN_DIR/screenshots/"
      n=$((n + 1))
    done
  done
  ok "$n screenshot(s) copied from $SHOTS"
else
  cat > "$RUN_DIR/screenshots/README.md" <<'SHOTS_EOF'
# Screenshots

Drop the console screenshots here, then re-run:

    bash scripts/import-evidence.sh

The rubric asks for these four:

| File name to use | What to capture |
|---|---|
| `bedrock-evaluations-results.png` | Bedrock console → Evaluations → your job → results page |
| `dynamodb-bug-reports.png` | DynamoDB console → `bug-report-tool-stack-bug-reports` → Explore items |
| `lambda-test-result.png` | Lambda console → `bug-report-tool-stack-create-bug-report` → Test tab, showing a `ticketId` and `"status": "OPEN"` |
| `chat-transcript.png` | A `chat.py` bug report showing the follow-up questions and the `[tool call] bugreports___create_bug_report` line |
SHOTS_EOF
  warn "no screenshots yet — see $RUN_DIR/screenshots/README.md"
fi

# ----------------------------------------------------------------- index ----
step "Writing INDEX.md"

SUMMARY="$RUN_DIR/run_summary.txt"
{
  echo "# Evidence — run $(printf '%02d' "$RUN_N")"
  echo
  echo "Imported from a CloudShell \`evidence.tar.gz\` bundle."
  echo
  if [ -f "$SUMMARY" ]; then
    echo '```'
    cat "$SUMMARY"
    echo '```'
    echo
  fi
  echo "## What each file proves"
  echo
  echo "| File | Rubric requirement |"
  echo "|---|---|"
  echo "| \`system_prompt.txt\` | The deliverable — classification, all three routes, the collection rules |"
  echo "| \`rendered_system_prompt.txt\` | The prompt as the harness received it, with \`{{FAQ}}\` substituted — the AgentCore stand-in for the 'FAQ Prompt node template showing embedded FAQ content' |"
  echo "| \`online_shop_faq.md\` | The FAQ, extended with a gift-card section |"
  echo "| \`harness-tests.json\` / \`flow-tests.json\` | Test suite, ≥1 case per route (21 total) |"
  echo "| \`output_eval_dataset.jsonl\` | The JSONL produced by \`generate-eval-dataset.py\` |"
  echo "| \`bug_report_transcript.txt\` | Multi-turn bug report with follow-up questions and the tool-call line |"
  echo "| \`dynamodb_bug_reports.json\` | Records created in \`bug-report-tool-stack-bug-reports\` |"
  echo "| \`eval-results/\` | Bedrock Evaluations output, downloaded from S3 |"
  echo "| \`eval_job.json\` | The evaluation job ARN and name |"
  echo "| \`screenshots/\` | Console screenshots |"
  echo
  echo "See [\`../../SUBMISSION.md\`](../../SUBMISSION.md) for the full rubric map."
} > "$RUN_DIR/INDEX.md"
ok "$RUN_DIR/INDEX.md"

# ------------------------------------------------------------------ git -----
step "Committing"

# The eval dataset and agentcore config are git-ignored as working files, but
# inside evidence/ they are the submission artefacts, so force-add them.
git add -A "$RUN_DIR"
git add -f "$RUN_DIR" 2>/dev/null || true

if git diff --cached --quiet; then
  warn "nothing new to commit"
  exit 0
fi

# Never let a real credential through, even by accident.
if git diff --cached | grep -qE 'AKIA[0-9A-Z]{16}|aws_secret_access_key'; then
  die "An AWS access key appears in the staged evidence. Remove it and retry."
fi

printf '  staged:\n'
git diff --cached --name-only | sed 's/^/    /'

git commit -q -m "Add evidence bundle from run $(printf '%02d' "$RUN_N")

Artefacts collected by cloudshell/run-all.sh: the system prompt and its
rendered form, the FAQ, both test-suite filenames, the evaluation dataset,
the bug-report transcript, a DynamoDB scan, and the Bedrock Evaluations
results.

See $RUN_DIR/INDEX.md for what each file proves, and SUBMISSION.md for the
rubric map."

ok "committed"

if git remote get-url origin >/dev/null 2>&1; then
  git push -q origin HEAD && ok "pushed to $(git remote get-url origin)"
else
  warn "no 'origin' remote — commit is local only"
fi

printf '\n%s✓ Evidence imported into %s%s\n\n' "$C_OK" "$RUN_DIR" "$C_OFF"
