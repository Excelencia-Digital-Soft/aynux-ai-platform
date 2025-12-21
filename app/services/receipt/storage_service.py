"""
Receipt Storage Service

Manages PDF receipt storage and URL generation for WhatsApp delivery.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)


class ReceiptStorageService:
    """
    Manages receipt file storage and URL generation.

    - Saves PDFs to static directory
    - Generates public URLs for WhatsApp delivery
    - Provides cleanup utilities for old files
    """

    def __init__(
        self,
        storage_path: str | Path,
        public_url_base: str,
    ):
        """
        Initialize the storage service.

        Args:
            storage_path: Directory path for storing PDF files
            public_url_base: Base URL for generating public file URLs
                            (e.g., "https://yourdomain.com")
        """
        self.storage_path = Path(storage_path)
        self.public_url_base = public_url_base.rstrip("/")

        # Ensure storage directory exists
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """Ensure the storage directory exists."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Receipt storage directory: {self.storage_path}")

    def store(self, pdf_bytes: bytes, payment_id: str) -> str:
        """
        Store a PDF receipt and return its public URL.

        Args:
            pdf_bytes: PDF content as bytes
            payment_id: MercadoPago payment ID for filename

        Returns:
            Public URL to access the PDF
        """
        # Generate unique filename with UUID to prevent enumeration
        unique_id = uuid4().hex[:8]
        timestamp = datetime.now(UTC).strftime("%Y%m%d")
        filename = f"recibo_{payment_id}_{timestamp}_{unique_id}.pdf"

        # Save file
        file_path = self.storage_path / filename
        file_path.write_bytes(pdf_bytes)

        logger.info(f"Receipt stored: {file_path} ({len(pdf_bytes)} bytes)")

        # Generate public URL
        # Assumes files are served from /static/receipts/
        public_url = f"{self.public_url_base}/static/receipts/{filename}"

        return public_url

    def get_file_path(self, filename: str) -> Path | None:
        """
        Get the full path for a receipt filename.

        Args:
            filename: Receipt filename

        Returns:
            Full path if file exists, None otherwise
        """
        file_path = self.storage_path / filename
        if file_path.exists():
            return file_path
        return None

    def delete(self, filename: str) -> bool:
        """
        Delete a receipt file.

        Args:
            filename: Receipt filename to delete

        Returns:
            True if deleted, False if not found
        """
        file_path = self.storage_path / filename
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Receipt deleted: {filename}")
            return True
        return False

    def cleanup_old_receipts(self, max_age_days: int = 30) -> int:
        """
        Remove receipts older than the specified age.

        Args:
            max_age_days: Maximum age in days to keep receipts

        Returns:
            Number of files deleted
        """
        cutoff = datetime.now(UTC).timestamp() - (max_age_days * 24 * 60 * 60)
        deleted_count = 0

        for file_path in self.storage_path.glob("recibo_*.pdf"):
            if file_path.stat().st_mtime < cutoff:
                file_path.unlink()
                deleted_count += 1
                logger.debug(f"Cleaned up old receipt: {file_path.name}")

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old receipts (>{max_age_days} days)")

        return deleted_count

    def list_receipts(self, limit: int = 100) -> list[dict]:
        """
        List recent receipts in storage.

        Args:
            limit: Maximum number of receipts to return

        Returns:
            List of receipt info dicts with filename, size, created_at
        """
        receipts = []

        files = sorted(
            self.storage_path.glob("recibo_*.pdf"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        for file_path in files[:limit]:
            stat = file_path.stat()
            receipts.append(
                {
                    "filename": file_path.name,
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                    "url": f"{self.public_url_base}/static/receipts/{file_path.name}",
                }
            )

        return receipts
