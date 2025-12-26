"""
Document Processing Integration

Provides document processing services for the application.
Supports: PDF, DOCX, TXT, MD
"""

from .document_extractor import DocumentExtractor
from .pdf_extractor import PDFExtractor

__all__ = ["DocumentExtractor", "PDFExtractor"]
