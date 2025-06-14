"""
AI Data Pipeline Service - Main Orchestrator.

This service orchestrates the complete pipeline from data extraction to vector store ingestion,
providing a unified interface for AI agents to access user-specific data.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.services.data_extraction_service import (
    DataExtractionService,
    UserDataContext,
    create_extraction_service_from_config,
)
from app.services.vector_store_ingestion_service import (
    VectorStoreDocument,
    VectorStoreIngestionService,
    create_ingestion_service_from_config,
)

logger = logging.getLogger(__name__)


# Data Models
class PipelineConfig(BaseModel):
    """Configuration for the AI data pipeline."""

    extraction_config: Dict[str, Any] = Field(default_factory=dict)
    ingestion_config: Dict[str, Any] = Field(default_factory=dict)
    default_chunk_size: int = 1000
    max_records_per_extraction: int = 10000
    enable_auto_refresh: bool = False
    refresh_interval_hours: int = 24


class PipelineExecutionContext(BaseModel):
    """Context for pipeline execution."""

    user_id: str
    tables: List[str]
    filters: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    chunk_size: int = 1000
    force_refresh: bool = False
    include_schema: bool = True


class PipelineResult(BaseModel):
    """Result of pipeline execution."""

    success: bool
    user_id: str
    tables_processed: List[str]
    total_documents_stored: int
    processing_time_seconds: float
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DataRetrievalContext(BaseModel):
    """Context for data retrieval for AI agents."""

    user_id: str
    query: str
    table_filters: Optional[List[str]] = None
    max_results: int = 10
    include_metadata: bool = True


class AIDataContext(BaseModel):
    """Enriched data context for AI agents."""

    user_id: str
    query: str
    relevant_documents: List[VectorStoreDocument]
    context_summary: str
    table_schemas: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Main Service
class AIDataPipelineService:
    """
    Main orchestrator service for the AI data pipeline.

    This service provides a unified interface for:
    1. Extracting data from various sources
    2. Processing and embedding the data
    3. Storing in vector stores
    4. Retrieving relevant data for AI agents
    """

    def __init__(
        self,
        extraction_service: DataExtractionService,
        ingestion_service: VectorStoreIngestionService,
        config: PipelineConfig,
    ):
        self.extraction_service = extraction_service
        self.ingestion_service = ingestion_service
        self.config = config
        self._last_refresh: Dict[str, datetime] = {}

    async def setup_user_data_pipeline(self, context: PipelineExecutionContext) -> PipelineResult:
        """
        Set up the complete data pipeline for a user.

        This method extracts data from specified tables, processes it,
        and stores it in the vector store for AI agent access.

        Args:
            context: Pipeline execution context

        Returns:
            PipelineResult with execution details
        """
        start_time = datetime.now()
        tables_processed = []
        total_documents = 0
        errors = []

        try:
            logger.info(f"Starting pipeline setup for user {context.user_id}")

            # Check if refresh is needed
            if not context.force_refresh and not self._needs_refresh(context.user_id):
                logger.info(f"Data for user {context.user_id} is still fresh, skipping refresh")
                return PipelineResult(
                    success=True,
                    user_id=context.user_id,
                    tables_processed=[],
                    total_documents_stored=0,
                    processing_time_seconds=0,
                    metadata={"skipped": True, "reason": "data_still_fresh"},
                )

            # Process each table
            for table_name in context.tables:
                try:
                    logger.info(f"Processing table {table_name} for user {context.user_id}")

                    # Create user data context
                    user_context = UserDataContext(
                        user_id=context.user_id,
                        table_name=table_name,
                        filters=context.filters.get(table_name, {}),
                        limit=self.config.max_records_per_extraction,
                        include_metadata=context.include_schema,
                    )

                    # Extract data
                    extracted_data = self.extraction_service.extract_user_data(user_context)

                    if not extracted_data.data:
                        logger.warning(f"No data found in table {table_name} for user {context.user_id}")
                        continue

                    # Ingest into vector store
                    ingestion_result = await self.ingestion_service.ingest_extracted_data(
                        extracted_data=extracted_data, user_id=context.user_id, chunk_size=context.chunk_size
                    )

                    if ingestion_result.success:
                        tables_processed.append(table_name)
                        total_documents += ingestion_result.documents_stored
                        logger.info(
                            f"Successfully processed {ingestion_result.documents_stored}"
                            f" documents from table {table_name}"
                        )
                    else:
                        errors.extend(ingestion_result.errors)
                        logger.error(f"Failed to ingest data from table {table_name}")

                except Exception as e:
                    error_msg = f"Error processing table {table_name}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)

            # Update last refresh time
            self._last_refresh[context.user_id] = datetime.now()

            processing_time = (datetime.now() - start_time).total_seconds()

            return PipelineResult(
                success=len(tables_processed) > 0,
                user_id=context.user_id,
                tables_processed=tables_processed,
                total_documents_stored=total_documents,
                processing_time_seconds=processing_time,
                errors=errors,
                metadata={
                    "total_tables_requested": len(context.tables),
                    "chunk_size": context.chunk_size,
                    "include_schema": context.include_schema,
                },
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"Pipeline setup failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

            return PipelineResult(
                success=False,
                user_id=context.user_id,
                tables_processed=tables_processed,
                total_documents_stored=total_documents,
                processing_time_seconds=processing_time,
                errors=errors,
            )

    async def get_ai_context(self, context: DataRetrievalContext) -> AIDataContext:
        """
        Retrieve and prepare data context for AI agents.

        This method searches the vector store for relevant user data
        and prepares it in a format suitable for AI agent consumption.

        Args:
            context: Data retrieval context

        Returns:
            AIDataContext with relevant data and metadata
        """
        try:
            logger.info(f"Retrieving AI context for user {context.user_id}, query: {context.query}")

            # Search for relevant documents
            relevant_docs = []

            if context.table_filters:
                # Search each specified table
                for table_name in context.table_filters:
                    docs = await self.ingestion_service.search_user_data(
                        query=context.query,
                        user_id=context.user_id,
                        table_filter=table_name,
                        limit=context.max_results // len(context.table_filters),
                    )
                    relevant_docs.extend(docs)
            else:
                # Search across all tables
                relevant_docs = await self.ingestion_service.search_user_data(
                    query=context.query, user_id=context.user_id, limit=context.max_results
                )

            # Create context summary
            context_summary = self._create_context_summary(relevant_docs, context.query)

            # Get table schemas if requested
            table_schemas = {}
            if context.include_metadata and relevant_docs:
                tables = set(
                    doc.metadata.get("source_table") for doc in relevant_docs if doc.metadata.get("source_table")
                )
                for table_name in tables:
                    try:
                        schema = self.extraction_service.get_table_info(table_name)
                        table_schemas[table_name] = schema.model_dump()
                    except Exception as e:
                        logger.warning(f"Could not get schema for table {table_name}: {e}")

            return AIDataContext(
                user_id=context.user_id,
                query=context.query,
                relevant_documents=relevant_docs,
                context_summary=context_summary,
                table_schemas=table_schemas,
                metadata={
                    "total_documents_found": len(relevant_docs),
                    "tables_searched": context.table_filters or "all",
                    "search_timestamp": datetime.now().isoformat(),
                },
            )

        except Exception as e:
            logger.error(f"Error retrieving AI context: {e}")
            return AIDataContext(
                user_id=context.user_id,
                query=context.query,
                relevant_documents=[],
                context_summary=f"Error retrieving context: {str(e)}",
                metadata={"error": str(e)},
            )

    async def refresh_user_data(
        self, user_id: str, tables: Optional[List[str]] = None, force: bool = False
    ) -> PipelineResult:
        """
        Refresh data for a specific user.

        Args:
            user_id: User ID to refresh data for
            tables: Optional list of specific tables to refresh
            force: Force refresh even if data is fresh

        Returns:
            PipelineResult with refresh details
        """
        # Get available tables if not specified
        if not tables:
            tables = self.extraction_service.get_available_tables()

        context = PipelineExecutionContext(
            user_id=user_id, tables=tables, force_refresh=force, chunk_size=self.config.default_chunk_size
        )

        return await self.setup_user_data_pipeline(context)

    async def delete_user_data(self, user_id: str) -> bool:
        """
        Delete all data for a specific user.

        Args:
            user_id: User ID to delete data for

        Returns:
            True if successful
        """
        try:
            success = await self.ingestion_service.delete_user_data(user_id)
            if success:
                # Remove from refresh tracking
                self._last_refresh.pop(user_id, None)
                logger.info(f"Successfully deleted all data for user {user_id}")
            return success
        except Exception as e:
            logger.error(f"Error deleting user data: {e}")
            return False

    def get_available_tables(self) -> List[str]:
        """Get list of all available tables for data extraction."""
        return self.extraction_service.get_available_tables()

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema information for a specific table."""
        schema = self.extraction_service.get_table_info(table_name)
        return schema.model_dump()

    def _needs_refresh(self, user_id: str) -> bool:
        """Check if user data needs refreshing."""
        if not self.config.enable_auto_refresh:
            return False

        last_refresh = self._last_refresh.get(user_id)
        if not last_refresh:
            return True

        hours_since_refresh = (datetime.now() - last_refresh).total_seconds() / 3600
        return hours_since_refresh >= self.config.refresh_interval_hours

    def _create_context_summary(self, documents: List[VectorStoreDocument], query: str) -> str:
        """Create a summary of the relevant context for AI agents."""
        if not documents:
            return f"No relevant data found for query: {query}"

        # Group documents by table
        table_groups = {}
        for doc in documents:
            table_name = doc.metadata.get("source_table", "unknown")
            if table_name not in table_groups:
                table_groups[table_name] = []
            table_groups[table_name].append(doc)

        summary_parts = [f"Found {len(documents)} relevant documents for query: '{query}'"]

        for table_name, table_docs in table_groups.items():
            schema_docs = [d for d in table_docs if d.metadata.get("type") == "schema"]
            data_docs = [d for d in table_docs if d.metadata.get("type") == "data"]

            summary_parts.append(f"\nTable: {table_name}")
            summary_parts.append(f"  - Schema documents: {len(schema_docs)}")
            summary_parts.append(f"  - Data documents: {len(data_docs)}")

            if data_docs:
                total_records = sum(d.metadata.get("record_count", 0) for d in data_docs)
                summary_parts.append(f"  - Total records: {total_records}")

        return "\n".join(summary_parts)


# Factory Functions
def create_ai_data_pipeline_service(config: Optional[Dict[str, Any]] = None) -> AIDataPipelineService:
    """Create an AI data pipeline service with default configuration."""
    config = config or {}

    # Create pipeline config
    pipeline_config = PipelineConfig(
        extraction_config=config.get("extraction", {}),
        ingestion_config=config.get("ingestion", {}),
        default_chunk_size=config.get("chunk_size", 1000),
        max_records_per_extraction=config.get("max_records", 10000),
        enable_auto_refresh=config.get("enable_auto_refresh", False),
        refresh_interval_hours=config.get("refresh_interval_hours", 24),
    )

    # Create services
    extraction_service = create_extraction_service_from_config(pipeline_config.extraction_config)
    ingestion_service = create_ingestion_service_from_config(pipeline_config.ingestion_config)

    return AIDataPipelineService(extraction_service, ingestion_service, pipeline_config)


# Convenience functions for AI agents
async def get_user_context_for_agent(
    user_id: str, query: str, table_filters: Optional[List[str]] = None, max_results: int = 5
) -> str:
    """
    Convenience function to get formatted context for AI agents.

    Args:
        user_id: User ID
        query: Search query
        table_filters: Optional table filters
        max_results: Maximum results to return

    Returns:
        Formatted context string for AI prompts
    """
    pipeline_service = create_ai_data_pipeline_service()

    context = DataRetrievalContext(user_id=user_id, query=query, table_filters=table_filters, max_results=max_results)

    ai_context = await pipeline_service.get_ai_context(context)

    # Format for AI consumption
    if not ai_context.relevant_documents:
        return f"No relevant user data found for query: {query}"

    formatted_parts = [
        f"User Context for {user_id}:",
        f"Query: {query}",
        f"Found {len(ai_context.relevant_documents)} relevant documents",
        "\nRelevant Data:",
    ]

    for i, doc in enumerate(ai_context.relevant_documents[:max_results], 1):
        table_name = doc.metadata.get("source_table", "unknown")
        doc_type = doc.metadata.get("type", "data")

        formatted_parts.append(f"\n{i}. [{table_name} - {doc_type}]")
        formatted_parts.append(doc.content[:500] + "..." if len(doc.content) > 500 else doc.content)

    return "\n".join(formatted_parts)


async def setup_user_pipeline(user_id: str, tables: Optional[List[str]] = None, force_refresh: bool = False) -> bool:
    """
    Convenience function to set up data pipeline for a user.

    Args:
        user_id: User ID
        tables: Optional list of tables to process
        force_refresh: Force refresh even if data is fresh

    Returns:
        True if successful
    """
    pipeline_service = create_ai_data_pipeline_service()

    if not tables:
        tables = pipeline_service.get_available_tables()

    context = PipelineExecutionContext(user_id=user_id, tables=tables, force_refresh=force_refresh)

    result = await pipeline_service.setup_user_data_pipeline(context)
    return result.success

