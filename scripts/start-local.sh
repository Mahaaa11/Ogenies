#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Starting L&C Emailing (Docker Compose)…"
docker compose up -d --build

echo ""
echo "Open:"
echo "  Web:       http://localhost:3001"
echo "  API:       http://localhost:8000/health"
echo "  phpMyAdmin http://localhost:8080"

