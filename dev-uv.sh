#!/bin/bash

# Colores para una mejor visualización
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Función para mostrar el estado
show_status() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

# Función para mostrar errores
show_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

# Función para mostrar éxito
show_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Función para mostrar advertencias
show_warning() {
  echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Verificar si UV está instalado
if ! command -v uv &>/dev/null; then
  show_error "UV no está instalado. Por favor, instálalo primero."
  echo "Puedes instalarlo con: curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "O con homebrew: brew install uv"
  exit 1
fi

# Verificar si el archivo .env existe
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    show_warning "Archivo .env no encontrado. Copiando desde .env.example..."
    cp .env.example .env
    show_warning "Por favor, edita el archivo .env con tus credenciales reales."
  else
    show_error "No se encontró ni .env ni .env.example. Por favor, crea un archivo .env para continuar."
    exit 1
  fi
fi

# Menú con opciones
show_menu() {
  echo -e "${BLUE}==== Bot ConversaShop - Menú de Desarrollo (UV) ====${NC}"
  echo "1. Instalar dependencias"
  echo "2. Iniciar servidor de desarrollo"
  echo "3. Ejecutar verificación de código (black, isort, ruff)"
  echo "4. Ejecutar pruebas (pytest)"
  echo "5. Actualizar dependencias"
  echo "6. Crear entorno virtual con UV"
  echo "7. Activar entorno virtual"
  echo "8. Sincronizar dependencias (lock file)"
  echo "0. Salir"
  echo -ne "${YELLOW}Selecciona una opción: ${NC}"
}

# Instalar dependencias
install_dependencies() {
  show_status "Instalando dependencias con UV..."
  uv pip sync pyproject.toml
  if [ $? -eq 0 ]; then
    show_success "Dependencias instaladas correctamente."
  else
    show_error "Error al instalar dependencias."
  fi
}

# Iniciar servidor de desarrollo
start_dev_server() {
  show_status "Iniciando servidor de desarrollo..."
  uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
}

# Ejecutar verificación de código
run_code_checks() {
  show_status "Ejecutando verificación de código..."
  echo "Running Black..."
  uv run black app
  echo "Running isort..."
  uv run isort app
  echo "Running Ruff..."
  uv run ruff check app --fix
  show_success "Verificación de código completada."
}

# Ejecutar pruebas
run_tests() {
  show_status "Ejecutando pruebas..."
  uv run pytest -v
}

# Actualizar dependencias
update_dependencies() {
  show_status "Actualizando dependencias..."
  uv pip compile pyproject.toml -o requirements.txt
  uv pip sync requirements.txt
  show_success "Dependencias actualizadas."
}

# Crear entorno virtual
create_venv() {
  show_status "Creando entorno virtual con UV..."
  uv venv
  show_success "Entorno virtual creado en .venv"
}

# Activar entorno virtual
activate_venv() {
  show_status "Para activar el entorno virtual, ejecuta:"
  echo "source .venv/bin/activate"
  echo ""
  echo "O si usas fish shell:"
  echo "source .venv/bin/activate.fish"
}

# Sincronizar dependencias
sync_dependencies() {
  show_status "Sincronizando dependencias..."
  uv pip compile pyproject.toml -o requirements.txt
  uv pip compile pyproject.toml --extra dev -o requirements-dev.txt
  uv pip sync requirements.txt requirements-dev.txt
  show_success "Dependencias sincronizadas."
}

# Lógica principal del menú
while true; do
  show_menu
  read -r option

  case $option in
  1) install_dependencies ;;
  2) start_dev_server ;;
  3) run_code_checks ;;
  4) run_tests ;;
  5) update_dependencies ;;
  6) create_venv ;;
  7) activate_venv ;;
  8) sync_dependencies ;;
  0)
    show_status "Saliendo..."
    exit 0
    ;;
  *)
    show_error "Opción inválida"
    ;;
  esac

  echo ""
  read -p "Presiona Enter para continuar..."
  clear
done