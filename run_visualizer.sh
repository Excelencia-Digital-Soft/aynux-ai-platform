#!/bin/bash

# Script para ejecutar el visualizador de agentes de Streamlit

set -e

echo "🚀 Iniciando Aynux Agent Visualizer..."
echo ""

# Verificar que estemos en el directorio correcto
if [ ! -f "streamlit_agent_visualizer.py" ]; then
    echo "❌ Error: No se encuentra streamlit_agent_visualizer.py"
    echo "   Asegúrate de ejecutar este script desde el directorio raíz del proyecto"
    exit 1
fi

# Verificar que exista .env
if [ ! -f ".env" ]; then
    echo "⚠️  Advertencia: No se encuentra .env"
    echo "   Copiando .env.example a .env..."
    cp .env.example .env
    echo "   ⚠️  Por favor, configura .env con tus credenciales"
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
echo "✅ Listo! Iniciando Streamlit..."
echo ""
echo "📊 El visualizador se abrirá en tu navegador"
echo "   URL: http://localhost:8501"
echo ""
echo "Presiona Ctrl+C para detener el servidor"
echo ""

# Ejecutar Streamlit
uv run streamlit run streamlit_agent_visualizer.py
