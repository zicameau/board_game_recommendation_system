#!/usr/bin/env bash
# Run on the VPS from /opt/bgg-rec-sys after a 502 — captures evidence BEFORE recreating containers.
# Usage: sudo bash deploy/scripts/triage-origin.sh
#        or:  bash /opt/bgg-rec-sys/deploy/scripts/triage-origin.sh

set -euo pipefail
cd /opt/bgg-rec-sys
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.deploy)
OUT="${TRIAGE_OUT:-./triage-$(date -u +%Y%m%dT%H%M%SZ).log}"

{
  echo "===== triage-origin $(date -uIs) ====="
  echo "hostname: $(hostname)"
  echo
  echo "=== docker compose ps -a ==="
  "${COMPOSE[@]}" ps -a
  echo
  echo "=== app container: state + health ==="
  docker inspect bgg-rec-sys-app-1 --format 'Status={{.State.Status}} OOM={{.State.OOMKilled}} Exit={{.State.ExitCode}} Started={{.State.StartedAt}} Finished={{.State.FinishedAt}} Error={{.State.Error}} Health={{json .State.Health}}' 2>/dev/null || echo "(no container or name mismatch — adjust name from compose ps)"
  echo
  echo "=== app: process list ==="
  docker top bgg-rec-sys-app-1 2>/dev/null || true
  echo
  echo "=== from caddy container → app:8000/healthz ==="
  docker exec bgg-rec-sys-caddy-1 wget -qSO- http://app:8000/healthz 2>&1 || true
  echo
  echo "=== app logs (last 500 lines) ==="
  "${COMPOSE[@]}" logs --no-color --tail=500 app 2>/dev/null || true
  echo
  echo "=== caddy logs — errors / upstream (last 200 lines, filtered) ==="
  "${COMPOSE[@]}" logs --no-color --tail=200 caddy 2>/dev/null | grep -iE 'error|502|refused|upstream|dial tcp' || echo "(no matching lines)"
  echo
  echo "=== caddy logs — last 80 lines raw ==="
  "${COMPOSE[@]}" logs --no-color --tail=80 caddy 2>/dev/null || true
  echo
  echo "=== kernel: recent OOM / kill hints (last 200 dmesg lines, filtered) ==="
  dmesg -T 2>/dev/null | tail -200 | grep -iE 'oom|killed process|out of memory' || echo "(none in tail)"
  echo
  echo "=== docker inspect app (full state JSON) ==="
  docker inspect bgg-rec-sys-app-1 --format '{{json .State}}' 2>/dev/null | head -c 4000 || true
  echo
} | tee "$OUT"

echo
echo "Saved: /opt/bgg-rec-sys/$(basename "$OUT")"
echo "Review this file before running: docker compose ... up -d --force-recreate app"
