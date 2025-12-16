#!/bin/bash
# docker-up.sh - Detecta entorno y ejecuta docker compose
# Resuelve el error "docker-credential-desktop not found" en servidores sin Docker Desktop

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detectar si docker-credential-desktop existe
if command -v docker-credential-desktop &> /dev/null; then
    # Entorno local con Docker Desktop
    echo -e "${GREEN}[docker-up]${NC} Docker Desktop detected, using native credentials"
    docker compose --profile tools up -d --build "$@"
else
    # Servidor sin Docker Desktop - usar config sin credStore
    echo -e "${YELLOW}[docker-up]${NC} No Docker Desktop, using temporary config without credStore"

    TEMP_DOCKER_CONFIG=$(mktemp -d)
    trap "rm -rf $TEMP_DOCKER_CONFIG" EXIT

    echo '{"auths":{}}' > "$TEMP_DOCKER_CONFIG/config.json"
    DOCKER_CONFIG="$TEMP_DOCKER_CONFIG" docker compose --profile tools up -d --build "$@"

    echo -e "${GREEN}[docker-up]${NC} Done!"
fi
