#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage:
  ./run.sh             Start the full MemoryEngine stack in the foreground with live logs
  ./run.sh up          Start the full MemoryEngine stack in the foreground with live logs
  ./run.sh up-detached Start the full MemoryEngine stack in detached mode
  ./run.sh down        Stop the stack
  ./run.sh restart     Rebuild and restart the stack in the foreground with live logs
  ./run.sh restart-detached Rebuild and restart the stack in detached mode
  ./run.sh logs [svc]  Stream logs for the whole stack or one service
  ./run.sh ps          Show compose service status
EOF
}

require_tool() {
  local tool_name="$1"
  if ! command -v "$tool_name" >/dev/null 2>&1; then
    echo "Missing required tool: $tool_name" >&2
    exit 1
  fi
}

compose() {
  docker compose "$@"
}

print_urls() {
  echo
  echo "MemoryEngine is starting."
  echo "Web:      http://localhost:3000"
  echo "API:      http://localhost:8001"
  echo "Postgres: localhost:5433"
  echo
}

require_tool docker
if ! compose version >/dev/null 2>&1; then
  echo "Docker Compose is required but not available via 'docker compose'." >&2
  exit 1
fi

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

ACTION="${1:-up}"

case "$ACTION" in
  up)
    print_urls
    compose up --build
    ;;
  up-detached)
    compose up -d --build
    print_urls
    compose ps
    ;;
  down)
    compose down
    ;;
  restart)
    print_urls
    compose up --build --force-recreate
    ;;
  restart-detached)
    compose up -d --build --force-recreate
    print_urls
    compose ps
    ;;
  logs)
    if [ $# -ge 2 ]; then
      compose logs -f --tail=100 "$2"
    else
      compose logs -f --tail=100
    fi
    ;;
  ps)
    compose ps
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown action: $ACTION" >&2
    echo >&2
    usage >&2
    exit 1
    ;;
esac
