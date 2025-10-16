#!/bin/bash

# Aynux Bot - Testing Suite Runner
# Este script facilita la ejecución de diferentes herramientas de testing

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Check Python
if ! command -v python &> /dev/null; then
    print_error "Python no está instalado"
    exit 1
fi

# Check dependencies
check_dependencies() {
    print_header "Verificando Dependencias"

    python -c "import rich" 2>/dev/null || {
        print_error "Rich no instalado. Instalando..."
        pip install rich
    }

    python -c "import streamlit" 2>/dev/null || {
        print_error "Streamlit no instalado. Instalando..."
        pip install streamlit
    }

    python -c "import plotly" 2>/dev/null || {
        print_error "Plotly no instalado. Instalando..."
        pip install plotly pandas
    }

    print_success "Todas las dependencias instaladas"
    echo ""
}

# Show menu
show_menu() {
    print_header "Aynux Bot - Testing Suite"

    echo "Selecciona una opción:"
    echo ""
    echo "  1) 🔍 Verificar Configuración de LangSmith"
    echo "  2) 💬 Chat Interactivo (Terminal)"
    echo "  3) 📊 Dashboard de Monitoreo (Web)"
    echo "  4) 🤖 Ejecutar Todos los Escenarios"
    echo "  5) 🎯 Ejecutar Escenario Específico"
    echo "  6) 🏷️  Ejecutar Escenarios por Tag"
    echo "  7) 📋 Listar Escenarios Disponibles"
    echo "  8) 📚 Ver Documentación"
    echo "  9) 🔧 Instalar/Actualizar Dependencias"
    echo "  0) 🚪 Salir"
    echo ""
    echo -n "Opción: "
}

# Main menu loop
main() {
    while true; do
        show_menu
        read -r option
        echo ""

        case $option in
            1)
                print_header "Verificación de LangSmith"
                python tests/test_langsmith_verification.py
                ;;
            2)
                print_header "Chat Interactivo"
                print_info "Presiona Ctrl+C para salir del chat"
                echo ""
                python tests/test_chat_interactive.py
                ;;
            3)
                print_header "Dashboard de Monitoreo"
                print_info "El dashboard se abrirá en http://localhost:8501"
                print_info "Presiona Ctrl+C para detener el servidor"
                echo ""
                streamlit run tests/monitoring_dashboard.py
                ;;
            4)
                print_header "Ejecutando Todos los Escenarios"
                python tests/test_scenarios.py all
                ;;
            5)
                print_header "Escenarios Disponibles"
                python tests/test_scenarios.py list
                echo ""
                echo -n "Ingresa el ID del escenario: "
                read -r scenario_id
                echo ""
                print_header "Ejecutando Escenario: $scenario_id"
                python tests/test_scenarios.py run "$scenario_id"
                ;;
            6)
                print_header "Tags Disponibles"
                echo "  • products"
                echo "  • categories"
                echo "  • support"
                echo "  • tracking"
                echo "  • credit"
                echo "  • promotions"
                echo "  • multi-turn"
                echo ""
                echo -n "Ingresa el tag: "
                read -r tag
                echo ""
                print_header "Ejecutando Escenarios con Tag: $tag"
                python tests/test_scenarios.py tag "$tag"
                ;;
            7)
                print_header "Listado de Escenarios"
                python tests/test_scenarios.py list
                ;;
            8)
                print_header "Documentación"
                echo "📖 Guías disponibles:"
                echo ""
                echo "  • Quick Start:        QUICKSTART_TESTING.md"
                echo "  • Guía Completa:      docs/TESTING_GUIDE.md"
                echo "  • README de Tests:    tests/readme.md"
                echo "  • Resumen:            TESTING_IMPLEMENTATION_SUMMARY.md"
                echo ""
                echo -n "¿Ver alguna guía? (q/g/r/s/n): "
                read -r doc_option

                case $doc_option in
                    q|Q)
                        less QUICKSTART_TESTING.md
                        ;;
                    g|G)
                        less docs/TESTING_GUIDE.md
                        ;;
                    r|R)
                        less tests/readme.md
                        ;;
                    s|S)
                        less TESTING_IMPLEMENTATION_SUMMARY.md
                        ;;
                    *)
                        print_info "Continuando..."
                        ;;
                esac
                ;;
            9)
                check_dependencies
                ;;
            0)
                print_success "¡Hasta luego!"
                exit 0
                ;;
            *)
                print_error "Opción inválida. Intenta nuevamente."
                ;;
        esac

        echo ""
        echo -n "Presiona Enter para continuar..."
        read -r
        clear
    done
}

# Check if dependencies should be auto-installed
if [ "$1" == "--install-deps" ]; then
    check_dependencies
    exit 0
fi

# Clear screen and start
clear
main
