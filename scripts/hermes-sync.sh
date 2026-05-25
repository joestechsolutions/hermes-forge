#!/usr/bin/env bash
#
# hermes-sync.sh — Daily auto-commit + push to GitHub
# Runs at midnight via cron: 0 0 * * * /home/lurkr/ai-platform/scripts/hermes-sync.sh
#
# PUSH_ALL=true  — also include ~/.hermes state files (state.db, sessions, snapshots)
# PUSH_ALL=false — only ai-platform code/config dirs
#
set -euo pipefail

REPO_DIR="/home/lurkr/ai-platform"
REMOTE="origin"
BRANCH="main"
USER_HOME="${HOME}"
PUSH_ALL="${PUSH_ALL:-true}"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
COMMIT_MSG="Daily sync ${TIMESTAMP}

Hermes Infrastructure Suite — auto-commit"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[SYNC]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERR]${NC} $*" >&2; }

cd "$REPO_DIR" || { err "Cannot cd to $REPO_DIR"; exit 1; }

log "Starting daily sync at ${TIMESTAMP}"

# Check git is clean
if ! git diff --quiet && git diff --cached --quiet; then
    STATUS="dirty"
else
    # Also check untracked files
    if [[ -n "$(git status --porcelain)" ]]; then
        STATUS="dirty"
    else
        STATUS="clean"
    fi
fi

log "Git status: ${STATUS}"

if [[ "$STATUS" == "clean" ]]; then
    log "Nothing to commit — repo already up to date."
    exit 0
fi

# Stage everything
git add -A

# Include Hermes state files if PUSH_ALL=true
if [[ "$PUSH_ALL" == "true" ]]; then
    log "Including Hermes state files..."
    # Hermes session state
    if [[ -d "${USER_HOME}/.hermes/sessions" ]]; then
        git add -f "${USER_HOME}/.hermes/sessions/" 2>/dev/null || warn "Could not add sessions"
    fi
    # Hermes state db (SQLite)
    if [[ -f "${USER_HOME}/.hermes/state.db" ]]; then
        git add -f "${USER_HOME}/.hermes/state.db" 2>/dev/null || warn "Could not add state.db"
    fi
    # Hermes response store
    if [[ -f "${USER_HOME}/.hermes/response_store.db" ]]; then
        git add -f "${USER_HOME}/.hermes/response_store.db" 2>/dev/null || warn "Could not add response_store.db"
    fi
    # Snapshots
    if [[ -d "${USER_HOME}/.hermes/snapshots" ]]; then
        git add -f "${USER_HOME}/.hermes/snapshots/" 2>/dev/null || warn "Could not add snapshots"
    fi
    # MemPalace data
    if [[ -d "${USER_HOME}/.mempalace" ]]; then
        git add -f "${USER_HOME}/.mempalace/" 2>/dev/null || warn "Could not add mempalace"
    fi
fi

# Count staged files
STAGED_COUNT=$(git status --porcelain | wc -l)
log "${STAGED_COUNT} file(s) changed — staging and committing..."

# Commit
git commit -m "$COMMIT_MSG" 2>/dev/null || {
    warn "Nothing to commit after staging."
    exit 0
}

# Push
log "Pushing to ${REMOTE}/${BRANCH}..."
if git push "$REMOTE" "$BRANCH" 2>&1; then
    log "Push complete: ${REMOTE}/${BRANCH}"
else
    err "Push failed — check network / authentication"
    exit 1
fi

log "Daily sync done at $(date '+%Y-%m-%d %H:%M:%S')"