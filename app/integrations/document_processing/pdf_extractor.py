"""
PDF Text Extraction Service

Service for extracting text content from PDF files.
Follows SRP: Single responsibility for PDF text extraction.
"""

import io
import logging
from pathlib import Path
from typing import Dict, Optional

try:
    from pypdf import PdfReader

    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    PdfReader = None  # type: ignore  # noqa
    logging.warning("pypdf not installed. Install with: pip install pypdf")

logger = logging.getLogger(__name__)


class PDFExtractor:
    """
    Service for extracting text from PDF files.

    Responsibilities:
    - Extract text from PDF bytes or file path
    - Extract metadata (title, author, pages)
    - Split by pages if needed
    - Handle errors gracefully

    Does NOT contain business logic (that's in Use Cases).
    """

    def __init__(self):
        """Initialize PDF extractor."""
        if not PYPDF_AVAILABLE:
            raise ImportError("pypdf is required for PDF extraction. " "Install with: pip install pypdf")

    def extract_text_from_bytes(self, pdf_bytes: bytes, extract_metadata: bool = True) -> Dict[str, any]:
        """
        Extract text and metadata from PDF bytes.

        Args:
            pdf_bytes: PDF file content as bytes
            extract_metadata: Whether to extract metadata (title, author, etc.)

        Returns:
            Dictionary with:
                - text: Full extracted text
                - pages: List of text per page
                - metadata: PDF metadata (if extract_metadata=True)
                - page_count: Number of pages

        Raises:
            ValueError: If PDF is invalid or cannot be read
        """
        try:
            # Read PDF from bytes
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)  # type: ignore  # PdfReader is checked in __init__

            # Extract text from all pages
            pages_text = []
            for page_num, page in enumerate(reader.pages, start=1):
                try:
                    page_text = page.extract_text()
                    pages_text.append(page_text)
                except Exception as e:
                    logger.warning(f"Error extracting text from page {page_num}: {e}")
                    pages_text.append("")

            # Combine all pages
            full_text = "\n\n".join(pages_text)

            # Extract metadata
            metadata = {}
            if extract_metadata and reader.metadata:
                metadata = {
                    "title": reader.metadata.get("/Title", ""),
                    "author": reader.metadata.get("/Author", ""),
                    "subject": reader.metadata.get("/Subject", ""),
                    "creator": reader.metadata.get("/Creator", ""),
                    "producer": reader.metadata.get("/Producer", ""),
                    "creation_date": str(reader.metadata.get("/CreationDate", "")),
                }

            result = {
                "text": full_text,
                "pages": pages_text,
                "page_count": len(pages_text),
                "metadata": metadata,
            }

            logger.info(f"Extracted {len(full_text)} characters from {len(pages_text)} pages")
            return result

        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise ValueError(f"Could not extract text from PDF: {str(e)}") from e

    def extract_text_from_file(self, file_path: str, extract_metadata: bool = True) -> Dict[str, any]:
        """
        Extract text and metadata from PDF file path.

        Args:
            file_path: Path to PDF file
            extract_metadata: Whether to extract metadata

        Returns:
            Dictionary with extracted text and metadata

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If PDF is invalid
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"PDF file not found: {file_path}")

            with open(file_path, "rb") as f:
                pdf_bytes = f.read()

            return self.extract_text_from_bytes(pdf_bytes, extract_metadata)

        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error reading PDF file {file_path}: {e}")
            raise ValueError(f"Could not read PDF file: {str(e)}") from e

    def validate_pdf(self, pdf_bytes: bytes) -> bool:
        """
        Validate if bytes represent a valid PDF file.

        Args:
            pdf_bytes: File content as bytes

        Returns:
            True if valid PDF, False otherwise
        """
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)  # type: ignore  # PdfReader is checked in __init__
            # Try to access pages to validate
            _ = len(reader.pages)
            return True
        except Exception as e:
            logger.debug(f"PDF validation failed: {e}")
            return False

    def extract_pages_range(self, pdf_bytes: bytes, start_page: int = 1, end_page: Optional[int] = None) -> str:
        """
        Extract text from a specific range of pages.

        Args:
            pdf_bytes: PDF content as bytes
            start_page: Starting page number (1-indexed)
            end_page: Ending page number (inclusive, None = last page)

        Returns:
            Extracted text from specified pages

        Raises:
            ValueError: If page range is invalid
        """
        try:
            result = self.extract_text_from_bytes(pdf_bytes, extract_metadata=False)
            pages = result["pages"]

            # Validate page range
            if start_page < 1 or start_page > len(pages):
                raise ValueError(f"Invalid start_page: {start_page}")

            end = end_page if end_page is not None else len(pages)
            if end < start_page or end > len(pages):
                raise ValueError(f"Invalid end_page: {end}")

            # Extract range (convert to 0-indexed)
            selected_pages = pages[start_page - 1 : end]
            return "\n\n".join(selected_pages)

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error extracting page range: {e}")
            raise ValueError(f"Could not extract pages: {str(e)}") from e
