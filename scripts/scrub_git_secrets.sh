#!/bin/bash
# scrub_git_secrets.sh — remove leaked secrets from the entire git history.
#
# ⚠️  DESTRUCTIVE: this rewrites EVERY commit's SHA. You will have to:
#     1. Force-push to origin (git push --force --all && git push --force --tags)
#     2. Ask every collaborator to re-clone or hard-reset their local copy
#     3. Rotate the secrets in their respective consoles (Snapchat etc.) — already
#        burned because they were public, the scrub only stops future bleed.
#
# Run from the repo root (NOT from a worktree).
#
# Prereqs:
#   pip install --user git-filter-repo
#
# Usage:
#   bash scripts/scrub_git_secrets.sh

set -euo pipefail

if ! command -v git-filter-repo >/dev/null 2>&1; then
    echo "✗ git-filter-repo is not installed. Run: pip install --user git-filter-repo"
    exit 1
fi

# Make sure we're at the repo root and on a clean tree.
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
if [ "$(git rev-parse --is-inside-work-tree)" != "true" ]; then
    echo "✗ not inside a git work tree"
    exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
    echo "✗ working tree has uncommitted changes. Commit or stash them first."
    exit 1
fi

# Create a backup tag at HEAD so the old history is recoverable locally.
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_REF="refs/backup/pre-scrub-${TIMESTAMP}"
git update-ref "$BACKUP_REF" HEAD
echo "✓ backup saved at $BACKUP_REF"

# Replacement file: any token on a left-hand side becomes the right-hand side
# in every blob across history. Edit this list if you discover more leaks.
REPLACE_FILE="$(mktemp)"
cat > "$REPLACE_FILE" <<'EOF'
f4f2c54fa34ca552b572==><REDACTED-SNAP-CLIENT-SECRET>
9f24e0ad-fdd0-4c8c-8b92-ca9f8e26cd77==><REDACTED-SNAP-CLIENT-ID>
0592263833==><REDACTED-ADMIN-PASSWORD>
EOF

echo "→ running git filter-repo (this rewrites every commit)…"
git filter-repo --replace-text "$REPLACE_FILE" --force

rm -f "$REPLACE_FILE"

echo
echo "✓ scrub complete. The local history has been rewritten."
echo
echo "Next steps (do these manually, only after verifying the diff):"
echo "  1. git log --oneline -10                 # sanity-check the new history"
echo "  2. git push --force --all origin         # publish the rewrite"
echo "  3. git push --force --tags origin        # if you have tags"
echo
echo "If anything looks wrong, restore the original history with:"
echo "  git update-ref refs/heads/<branch> $BACKUP_REF"
