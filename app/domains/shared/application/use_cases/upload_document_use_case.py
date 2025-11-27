"""
Upload Document Use Cases

Use cases for uploading documents (PDF/text) to the knowledge base.
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.shared.application.use_cases.knowledge import (
    CreateKnowledgeUseCase,
)
from app.integrations.document_processing import PDFExtractor

logger = logging.getLogger(__name__)


class UploadPDFUseCase:
    """
    Use Case: Upload PDF Document to Knowledge Base

    Handles uploading PDF files, extracting text, and storing in knowledge base.

    Responsibilities:
    - Validate PDF file
    - Extract text from PDF
    - Create knowledge document with extracted content
    - Generate embeddings automatically

    Follows SRP: Single responsibility for PDF upload workflow
    """

    def __init__(
        self,
        db: AsyncSession,
        pdf_extractor: Optional[PDFExtractor] = None,
        create_knowledge_uc: Optional[CreateKnowledgeUseCase] = None,
    ):
        """
        Initialize upload PDF use case.

        Args:
            db: Database session
            pdf_extractor: PDF extraction service (optional)
            create_knowledge_uc: Knowledge creation use case (optional)
        """
        self.db = db
        self.pdf_extractor = pdf_extractor or PDFExtractor()
        self.create_knowledge_uc = create_knowledge_uc or CreateKnowledgeUseCase(db)

    async def execute(
        self,
        pdf_bytes: bytes,
        title: Optional[str] = None,
        document_type: str = "general",
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Upload PDF and create knowledge document.

        Args:
            pdf_bytes: PDF file content as bytes
            title: Document title (if None, extracted from PDF metadata)
            document_type: Type of document (default: "general")
            category: Optional category
            tags: Optional list of tags
            metadata: Optional additional metadata

        Returns:
            Created knowledge document as dictionary

        Raises:
            ValueError: If PDF is invalid or extraction fails

        Example:
            use_case = UploadPDFUseCase(db)
            with open("document.pdf", "rb") as f:
                pdf_bytes = f.read()

            result = await use_case.execute(
                pdf_bytes=pdf_bytes,
                title="Product Manual",
                document_type="faq",
                tags=["product", "manual"]
            )
        """
        try:
            # 1. Validate PDF
            if not self.pdf_extractor.validate_pdf(pdf_bytes):
                raise ValueError("Invalid PDF file")

            # 2. Extract text and metadata from PDF
            logger.info("Extracting text from PDF...")
            extraction_result = self.pdf_extractor.extract_text_from_bytes(pdf_bytes, extract_metadata=True)

            extracted_text = extraction_result["text"]
            pdf_metadata = extraction_result["metadata"]
            page_count = extraction_result["page_count"]

            # Validate extracted text
            if not extracted_text or len(extracted_text.strip()) < 50:
                raise ValueError(
                    "PDF text extraction resulted in insufficient content "
                    f"(minimum 50 characters required, got {len(extracted_text)})"
                )

            # 3. Prepare knowledge document data
            # Use provided title or extract from PDF metadata
            doc_title = title or pdf_metadata.get("title") or "Untitled PDF Document"

            # Merge metadata
            combined_metadata = metadata or {}
            combined_metadata.update(
                {
                    "source": "pdf_upload",
                    "pdf_pages": page_count,
                    "pdf_title": pdf_metadata.get("title", ""),
                    "pdf_author": pdf_metadata.get("author", ""),
                    "pdf_subject": pdf_metadata.get("subject", ""),
                }
            )

            knowledge_data = {
                "title": doc_title,
                "content": extracted_text,
                "document_type": document_type,
                "category": category,
                "tags": tags or [],
                "meta_data": combined_metadata,
                "active": True,
            }

            # 4. Create knowledge document (with auto-embedding)
            logger.info(f"Creating knowledge document: {doc_title}")
            result = await self.create_knowledge_uc.execute(
                knowledge_data=knowledge_data,
                auto_embed=True,
            )

            logger.info(f"Successfully uploaded PDF: {doc_title} " f"({page_count} pages, {len(extracted_text)} chars)")

            return result

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Error uploading PDF: {e}")
            raise ValueError(f"Failed to upload PDF: {str(e)}") from e


class UploadTextUseCase:
    """
    Use Case: Upload Text Content to Knowledge Base

    Handles uploading plain text or markdown content to knowledge base.

    Responsibilities:
    - Validate text content
    - Create knowledge document
    - Generate embeddings automatically

    Follows SRP: Single responsibility for text upload workflow
    """

    def __init__(
        self,
        db: AsyncSession,
        create_knowledge_uc: Optional[CreateKnowledgeUseCase] = None,
    ):
        """
        Initialize upload text use case.

        Args:
            db: Database session
            create_knowledge_uc: Knowledge creation use case (optional)
        """
        self.db = db
        self.create_knowledge_uc = create_knowledge_uc or CreateKnowledgeUseCase(db)

    async def execute(
        self,
        content: str,
        title: str,
        document_type: str = "general",
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Upload text content and create knowledge document.

        Args:
            content: Text content (plain text or markdown)
            title: Document title (required)
            document_type: Type of document (default: "general")
            category: Optional category
            tags: Optional list of tags
            metadata: Optional additional metadata

        Returns:
            Created knowledge document as dictionary

        Raises:
            ValueError: If validation fails

        Example:
            use_case = UploadTextUseCase(db)
            result = await use_case.execute(
                content="This is important information about our product...",
                title="Product Information",
                document_type="faq",
                tags=["product", "info"]
            )
        """
        try:
            # 1. Validate inputs
            if not title or len(title.strip()) < 3:
                raise ValueError("Title must be at least 3 characters")

            if not content or len(content.strip()) < 50:
                raise ValueError(f"Content must be at least 50 characters (got {len(content.strip())})")

            # 2. Prepare knowledge document data
            combined_metadata = metadata or {}
            combined_metadata["source"] = "text_upload"

            knowledge_data = {
                "title": title.strip(),
                "content": content.strip(),
                "document_type": document_type,
                "category": category,
                "tags": tags or [],
                "meta_data": combined_metadata,
                "active": True,
            }

            # 3. Create knowledge document (with auto-embedding)
            logger.info(f"Creating knowledge document from text: {title}")
            result = await self.create_knowledge_uc.execute(
                knowledge_data=knowledge_data,
                auto_embed=True,
            )

            logger.info(f"Successfully uploaded text: {title} ({len(content)} chars)")

            return result

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Error uploading text: {e}")
            raise ValueError(f"Failed to upload text: {str(e)}") from e


class BatchUploadDocumentsUseCase:
    """
    Use Case: Batch Upload Multiple Documents

    Handles uploading multiple documents (PDFs or text) in a single operation.

    Responsibilities:
    - Process multiple documents sequentially
    - Track success/failure for each document
    - Return summary of batch upload

    Follows SRP: Single responsibility for batch upload coordination
    """

    def __init__(
        self,
        db: AsyncSession,
        upload_pdf_uc: Optional[UploadPDFUseCase] = None,
        upload_text_uc: Optional[UploadTextUseCase] = None,
    ):
        """
        Initialize batch upload use case.

        Args:
            db: Database session
            upload_pdf_uc: PDF upload use case (optional)
            upload_text_uc: Text upload use case (optional)
        """
        self.db = db
        self.upload_pdf_uc = upload_pdf_uc or UploadPDFUseCase(db)
        self.upload_text_uc = upload_text_uc or UploadTextUseCase(db)

    async def execute(self, documents: list[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Upload multiple documents in batch.

        Args:
            documents: List of document dictionaries, each with:
                - type: "pdf" or "text"
                - content: PDF bytes (for PDF) or text content (for text)
                - title: Document title
                - document_type: Optional document type
                - category: Optional category
                - tags: Optional tags list
                - metadata: Optional metadata dict

        Returns:
            Dictionary with:
                - total: Total documents processed
                - successful: Number of successful uploads
                - failed: Number of failed uploads
                - results: List of results for each document
                - errors: List of errors (if any)

        Example:
            use_case = BatchUploadDocumentsUseCase(db)
            result = await use_case.execute([
                {
                    "type": "text",
                    "content": "Document 1 content...",
                    "title": "Document 1",
                    "document_type": "faq",
                },
                {
                    "type": "pdf",
                    "content": pdf_bytes,
                    "title": "Document 2",
                    "document_type": "general",
                }
            ])
        """
        results = []
        errors = []
        successful = 0
        failed = 0

        for i, doc in enumerate(documents):
            try:
                doc_type = doc.get("type", "text")

                if doc_type == "pdf":
                    result = await self.upload_pdf_uc.execute(
                        pdf_bytes=doc["content"],
                        title=doc.get("title"),
                        document_type=doc.get("document_type", "general"),
                        category=doc.get("category"),
                        tags=doc.get("tags"),
                        metadata=doc.get("metadata"),
                    )
                elif doc_type == "text":
                    result = await self.upload_text_uc.execute(
                        content=doc["content"],
                        title=doc["title"],
                        document_type=doc.get("document_type", "general"),
                        category=doc.get("category"),
                        tags=doc.get("tags"),
                        metadata=doc.get("metadata"),
                    )
                else:
                    raise ValueError(f"Unknown document type: {doc_type}")

                results.append(result)
                successful += 1
                logger.info(f"Batch upload: Document {i+1}/{len(documents)} successful")

            except Exception as e:
                failed += 1
                error_msg = f"Document {i+1} failed: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
                results.append(None)

        summary = {
            "total": len(documents),
            "successful": successful,
            "failed": failed,
            "results": results,
            "errors": errors,
        }

        logger.info(f"Batch upload completed: {successful}/{len(documents)} successful")

        return summary
