#!/bin/bash

# Run Streamlit Knowledge Manager
# This script launches the knowledge base and agent configuration manager

echo "🚀 Starting Knowledge Base & Agent Configuration Manager..."
echo "📚 Access the UI at: http://localhost:8501"
echo ""

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit is not installed"
    echo "Installing streamlit..."
    pip install streamlit
fi

# Run streamlit app
streamlit run streamlit_knowledge_manager.py \
    --server.port 8501 \
    --server.address localhost \
    --browser.gatherUsageStats false
