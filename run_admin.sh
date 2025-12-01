#!/bin/bash

# Script para ejecutar el Aynux Admin Dashboard (Streamlit unificado)
# Incluye: Chat Visualizer, Knowledge Base, Excelencia Management

set -e

echo "🚀 Iniciando Aynux Admin Dashboard..."
echo ""

# Verificar que estemos en el directorio correcto
if [ ! -d "streamlit_admin" ]; then
    echo "❌ Error: No se encuentra el directorio streamlit_admin"
    echo "   Asegúrate de ejecutar este script desde el directorio raíz del proyecto"
    exit 1
fi

# Verificar que exista .env
if [ ! -f ".env" ]; then
    echo "⚠️  Advertencia: No se encuentra .env"
    if [ -f ".env.example" ]; then
        echo "   Copiando .env.example a .env..."
        cp .env.example .env
        echo "   ⚠️  Por favor, configura .env con tus credenciales"
    fi
fi

# Instalar dependencias si es necesario
echo "📦 Verificando dependencias..."
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv no está instalado"
    echo "   Instala uv con: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Sync dependencies
echo "🔄 Sincronizando dependencias..."
uv sync

echo ""
echo "✅ Listo! Iniciando Streamlit Admin Dashboard..."
echo ""
echo "📊 Accede al dashboard en: http://localhost:8501"
echo ""
echo "Páginas disponibles:"
echo "  🤖 Chat Visualizer    - Probar chat y ver flujo de agentes"
echo "  📚 Knowledge Base     - Explorar y editar documentos"
echo "  📤 Upload Documents   - Subir PDFs y texto"
echo "  🔧 Embeddings         - Gestionar embeddings"
echo "  🏢 Excelencia         - Módulos y demos"
echo "  ⚙️  Agent Config       - Configuración de agentes"
echo "  📊 Statistics         - Estadísticas"
echo ""
echo "Presiona Ctrl+C para detener el servidor"
echo ""

# Ejecutar Streamlit
uv run streamlit run streamlit_admin/app.py \
    --server.port 8501 \
    --server.address localhost \
    --browser.gatherUsageStats false
