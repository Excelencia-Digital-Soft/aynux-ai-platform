#!/bin/bash

# Colores para mejor visualización
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Ejecutando pruebas unitarias ===${NC}"
python -m pytest tests/unit -v

echo -e "\n${YELLOW}=== Ejecutando pruebas de integración ===${NC}"
python -m pytest tests/integration -v

echo -e "\n${GREEN}¡Pruebas completadas!${NC}"
