#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
mkdir -p "$ROOT/var/logs"
STAMP="$(date +%Y%m%d-%H%M%S)"
# Use an isolated per-run output so custom paths cannot deploy an old artifact.
ARTIFACT_DIR="$ROOT/var/render-$STAMP"
"$PYTHON" "$ROOT/refresh.py" "$@" --output "$ARTIFACT_DIR" 2>&1 | tee "$ROOT/var/logs/refresh-$STAMP.log"

if [[ "${FREETRADE_DEPLOY:-0}" != "1" ]]; then
  exit 0
fi
: "${FREETRADE_REMOTE:?Set user@host}"
: "${FREETRADE_REMOTE_DIR:?Set remote static directory}"
: "${FREETRADE_PUBLIC_URL:?Set public HTTPS URL}"
: "${FREETRADE_SSH_KEY:?Set SSH key path}"
[[ "$FREETRADE_REMOTE" =~ ^[a-zA-Z0-9_.-]+@[a-zA-Z0-9_.-]+$ ]] || exit 2
[[ "$FREETRADE_REMOTE_DIR" =~ ^/[a-zA-Z0-9_./-]+$ ]] || exit 2
[[ "$FREETRADE_PUBLIC_URL" == https://* ]] || exit 2
ARTIFACT="$ARTIFACT_DIR/index.html"
scp -i "$FREETRADE_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=yes \
  "$ARTIFACT" "$FREETRADE_REMOTE:$FREETRADE_REMOTE_DIR/.index-$STAMP.html"
ssh -i "$FREETRADE_SSH_KEY" -o BatchMode=yes -o StrictHostKeyChecking=yes \
  "$FREETRADE_REMOTE" \
  "mv '$FREETRADE_REMOTE_DIR/.index-$STAMP.html' '$FREETRADE_REMOTE_DIR/index.html'"
"$PYTHON" "$ROOT/scripts/verify_site.py" "$FREETRADE_PUBLIC_URL" --expected "$ARTIFACT"
