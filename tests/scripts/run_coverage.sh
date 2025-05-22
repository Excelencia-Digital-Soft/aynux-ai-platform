#!/bin/bash

# Colores para mejor visualización
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Ejecutando pruebas con cobertura ===${NC}"
python -m pytest --cov=app tests/ --cov-report=term --cov-report=html

echo -e "\n${GREEN}¡Informe de cobertura generado!${NC}"
echo -e "Puedes ver el informe detallado en: htmlcov/index.html"
