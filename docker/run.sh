#!/bin/bash
# Wrapper for docker compose — sets DOCKER_API_VERSION to avoid
# "client version X is too new" errors on Jetson setups where
# the Docker client is newer than the daemon.
export DOCKER_API_VERSION=1.43

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec docker compose -f "$SCRIPT_DIR/docker-compose.yml" "$@"
