#!/bin/bash
# Immediate rollback script to revert to the working local model baseline
set -e

echo "=== Rolling back to local baseline... ==="
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# 1. Checkout backup branch
git checkout backup-local-working || git checkout local-model-baseline

# 2. Restart backend
echo "Restarting backend..."
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
sleep 1
cd "$DIR/backend"
nohup ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/empath_backend.log 2>&1 &

echo "=== Rollback complete! System is running local model baseline on port 8000. ==="
