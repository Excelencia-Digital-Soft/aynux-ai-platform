"""
Upload Documents - PDF and Text Upload

Interactive UI for:
- Uploading PDF documents
- Uploading text content
"""

import sys
from pathlib import Path

import streamlit as st

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from lib.api_client import upload_pdf, upload_text
from lib.session_state import init_session_state

init_session_state()

st.title("📤 Subir Documentos")
st.markdown("Sube archivos PDF o contenido de texto a la base de conocimiento.")

# Tabs
tab_pdf, tab_text = st.tabs(["📄 Subir PDF", "✍️ Subir Texto"])

# ============================================================================
# Tab: Upload PDF
# ============================================================================

with tab_pdf:
    st.subheader("📄 Subir Documento PDF")
    st.markdown("Sube archivos PDF para extraer texto y almacenar en la base de conocimiento.")

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded_file = st.file_uploader("Selecciona un archivo PDF", type=["pdf"], help="Selecciona un archivo PDF para subir")

    with col2:
        document_type = st.selectbox(
            "Tipo de Documento",
            ["general", "mission_vision", "contact_info", "software_catalog", "faq", "clients", "success_stories"],
            key="pdf_doc_type",
        )

    title = st.text_input("Título (opcional)", help="Deja vacío para extraer de los metadatos del PDF", key="pdf_title")

    col3, col4 = st.columns(2)
    with col3:
        category = st.text_input("Categoría (opcional)", key="pdf_category")
    with col4:
        tags = st.text_input("Etiquetas (separadas por coma)", placeholder="ej: producto,manual,tutorial", key="pdf_tags")

    if st.button("📤 Subir PDF", type="primary", disabled=uploaded_file is None):
        if uploaded_file is not None:
            with st.spinner("Subiendo PDF..."):
                result = upload_pdf(
                    file=uploaded_file,
                    title=title if title else None,
                    document_type=document_type,
                    category=category if category else None,
                    tags=tags,
                )

                if result:
                    st.success("✅ ¡PDF subido exitosamente!")
                    st.json(result)

# ============================================================================
# Tab: Upload Text
# ============================================================================

with tab_text:
    st.subheader("✍️ Subir Contenido de Texto")
    st.markdown("Sube texto plano o contenido markdown a la base de conocimiento.")

    title = st.text_input("Título *", placeholder="Título del documento (requerido)", key="text_title")

    col1, col2 = st.columns(2)
    with col1:
        document_type = st.selectbox(
            "Tipo de Documento",
            ["general", "mission_vision", "contact_info", "software_catalog", "faq", "clients", "success_stories"],
            key="text_doc_type",
        )
    with col2:
        category = st.text_input("Categoría (opcional)", key="text_category")

    tags_input = st.text_input("Etiquetas (separadas por coma)", placeholder="ej: producto,info,tutorial", key="text_tags")

    content = st.text_area(
        "Contenido *",
        height=300,
        placeholder="Escribe tu contenido de texto aquí (mínimo 50 caracteres)...",
        help="Formato texto plano o markdown soportado",
        key="text_content",
    )

    character_count = len(content)
    st.caption(f"Caracteres: {character_count} (mínimo: 50)")

    if st.button("📤 Subir Texto", type="primary", disabled=not title or character_count < 50):
        tags_list = [tag.strip() for tag in tags_input.split(",") if tag.strip()]

        with st.spinner("Subiendo texto..."):
            result = upload_text(
                content=content,
                title=title,
                document_type=document_type,
                category=category if category else None,
                tags=tags_list,
            )

            if result:
                st.success("✅ ¡Texto subido exitosamente!")
                st.json(result)

# Sidebar info
st.sidebar.markdown("---")
st.sidebar.subheader("📤 Subir Documentos")
st.sidebar.markdown(
    """
Agrega nuevos documentos a la base de conocimiento
de Excelencia para mejorar las respuestas del chatbot.

**Formatos soportados:**
- 📄 **PDF**: Extracción automática de texto
- ✍️ **Texto**: Texto plano o Markdown

**Proceso:**
1. Selecciona el tipo de documento
2. Agrega metadatos (título, categoría, etiquetas)
3. El contenido se procesa automáticamente
4. Se genera el embedding para búsqueda semántica
"""
)

st.sidebar.markdown("### Tipos de Documento")
st.sidebar.markdown(
    """
- **Misión y Visión**: Valores de la empresa
- **Información de Contacto**: Datos de contacto
- **Catálogo de Software**: Productos y módulos
- **FAQ**: Preguntas frecuentes
- **Clientes**: Información de clientes
- **Casos de Éxito**: Estudios de caso
- **General**: Información general
"""
)
