#!/usr/bin/env bash
# Lance la stack L&C Emailing en local (backend + frontend).
# Usage: bash dev.sh
set -e

PROJECT="/Users/macbookpro/Documents/New project"
cd "$PROJECT"

# --- Backend (FastAPI sur :8000) ---
if lsof -ti tcp:8000 >/dev/null 2>&1; then
  echo "[backend] deja en route sur :8000 — on ne le relance pas"
else
  echo "[backend] demarrage sur :8000..."
  set -a
  # shellcheck disable=SC1091
  [ -f .env ] && source .env
  set +a
  # shellcheck disable=SC1091
  source .venv/bin/activate
  nohup python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload \
    >/tmp/lnc-backend.log 2>&1 &
  echo "[backend] PID=$! — logs: /tmp/lnc-backend.log"
  sleep 1
fi

# --- Frontend (Next.js sur :3001) ---
if lsof -ti tcp:3001 >/dev/null 2>&1; then
  echo "[frontend] deja en route sur :3001 — on ne le relance pas"
  echo "Ouvre http://localhost:3001 dans le navigateur."
  exit 0
fi

echo "[frontend] demarrage sur :3001 (Ctrl-C pour stopper)..."
cd "$PROJECT/frontend"
# Best-effort: monter la limite FDs pour eviter EMFILE de Turbopack.
# On essaie 10240, puis 4096 en repli ; on ne plante pas si rien ne passe.
ulimit -n 10240 2>/dev/null || ulimit -n 4096 2>/dev/null || true
echo "[frontend] ulimit -n = $(ulimit -n)"
export NEXT_PUBLIC_API_BASE="http://127.0.0.1:8000"
export INTERNAL_API_BASE="http://127.0.0.1:8000"
exec npm run dev -- --hostname 127.0.0.1 --port 3001
