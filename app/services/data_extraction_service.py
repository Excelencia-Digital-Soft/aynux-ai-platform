"""
Dynamic Data Extraction Service for Vector Store Integration.

This service provides dynamic table schema inspection and data extraction
capabilities for AI agent integration through vector stores.
"""

import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Protocol, Union
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Data Models
class ColumnInfo(BaseModel):
    """Information about a database column."""

    name: str
    type: str
    nullable: bool
    primary_key: bool = False
    foreign_key: Optional[str] = None
    default: Optional[Any] = None


class TableSchema(BaseModel):
    """Schema information for a database table."""

    name: str
    columns: List[ColumnInfo]
    indexes: List[str] = Field(default_factory=list)
    foreign_keys: Dict[str, str] = Field(default_factory=dict)


class ExtractedData(BaseModel):
    """Container for extracted table data with metadata."""

    table_name: str
    table_schema: TableSchema
    data: List[Dict[str, Any]]
    extraction_timestamp: datetime = Field(default_factory=datetime.now)
    total_records: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UserDataContext(BaseModel):
    """Context for user-specific data extraction."""

    user_id: str
    table_name: str
    filters: Dict[str, Any] = Field(default_factory=dict)
    limit: Optional[int] = None
    include_metadata: bool = True


# Abstract Interfaces
class DataSourceInspector(Protocol):
    """Protocol for data source schema inspection."""

    def get_table_names(self) -> List[str]:
        """Get list of available table names."""
        ...

    def get_table_schema(self, table_name: str) -> TableSchema:
        """Get schema information for a specific table."""
        ...

    def validate_table_exists(self, table_name: str) -> bool:
        """Check if table exists in the data source."""
        ...


class DataExtractor(Protocol):
    """Protocol for data extraction from various sources."""

    def extract_table_data(
        self, table_name: str, filters: Optional[Dict[str, Any]] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Extract data from a table with optional filtering."""
        ...

    def extract_user_specific_data(self, context: UserDataContext) -> List[Dict[str, Any]]:
        """Extract data specific to a user context."""
        ...


class DataSerializer(ABC):
    """Abstract base class for data serialization."""

    @abstractmethod
    def serialize(self, data: Any) -> Any:
        """Serialize data to a JSON-compatible format."""
        pass


# Concrete Implementations
class SQLAlchemyInspector:
    """SQLAlchemy-based database schema inspector."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self.inspector = inspect(engine)

    def get_table_names(self) -> List[str]:
        """Get list of available table names."""
        try:
            return self.inspector.get_table_names()
        except Exception as e:
            logger.error(f"Error getting table names: {e}")
            return []

    def get_table_schema(self, table_name: str) -> TableSchema:
        """Get schema information for a specific table."""
        try:
            columns = self.inspector.get_columns(table_name)
            indexes = self.inspector.get_indexes(table_name)
            foreign_keys = self.inspector.get_foreign_keys(table_name)
            primary_keys = self.inspector.get_primary_keys(table_name)  # type: ignore

            column_info = []
            fk_map = {}

            # Process foreign keys
            for fk in foreign_keys:
                for local_col, ref_col in zip(fk["constrained_columns"], fk["referred_columns"]):
                    fk_map[local_col] = f"{fk['referred_table']}.{ref_col}"

            # Process columns
            for col in columns:
                column_info.append(
                    ColumnInfo(
                        name=col["name"],
                        type=str(col["type"]),
                        nullable=col["nullable"],
                        primary_key=col["name"] in primary_keys,
                        foreign_key=fk_map.get(col["name"]),
                        default=col.get("default"),
                    )
                )

            return TableSchema(
                name=table_name, columns=column_info, indexes=[idx["name"] for idx in indexes], foreign_keys=fk_map
            )

        except Exception as e:
            logger.error(f"Error getting schema for table {table_name}: {e}")
            raise

    def validate_table_exists(self, table_name: str) -> bool:
        """Check if table exists in the database."""
        return table_name in self.get_table_names()


class SQLAlchemyExtractor:
    """SQLAlchemy-based data extractor."""

    def __init__(self, engine: Engine):
        self.engine = engine

    def extract_table_data(
        self, table_name: str, filters: Optional[Dict[str, Any]] = None, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Extract data from a table with optional filtering."""
        try:
            with Session(self.engine) as session:
                # Build base query
                query = f"SELECT * FROM {table_name}"
                params = {}

                # Add filters
                if filters:
                    where_conditions = []
                    for key, value in filters.items():
                        if value is not None:
                            where_conditions.append(f"{key} = :filter_{key}")
                            params[f"filter_{key}"] = value

                    if where_conditions:
                        query += " WHERE " + " AND ".join(where_conditions)

                # Add limit
                if limit:
                    query += f" LIMIT {limit}"

                result = session.execute(text(query), params)

                # Convert to list of dictionaries
                columns = result.keys()
                data = []
                for row in result:
                    row_dict = {}
                    for i, value in enumerate(row):
                        row_dict[columns[i]] = self._serialize_value(value)  # type: ignore
                    data.append(row_dict)

                return data

        except Exception as e:
            logger.error(f"Error extracting data from table {table_name}: {e}")
            raise

    def extract_user_specific_data(self, context: UserDataContext) -> List[Dict[str, Any]]:
        """Extract data specific to a user context."""
        # Add user_id to filters if not present
        filters = context.filters.copy()

        # Try to add user filtering if possible
        user_columns = ["user_id", "customer_id", "phone_number", "created_by"]
        for col in user_columns:
            if col not in filters:
                filters[col] = context.user_id
                break

        return self.extract_table_data(table_name=context.table_name, filters=filters, limit=context.limit)

    def _serialize_value(self, value: Any) -> Any:
        """Convert database values to JSON-serializable format."""
        if value is None:
            return None
        elif isinstance(value, (datetime, date)):
            return value.isoformat()
        elif isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, UUID):
            return str(value)
        elif isinstance(value, (list, dict)):
            return value
        else:
            return str(value)


class JSONDataSerializer(DataSerializer):
    """JSON data serializer for vector store compatibility."""

    def serialize(self, data: ExtractedData) -> Dict[str, Any]:
        """Serialize extracted data to JSON format."""
        return {
            "table_name": data.table_name,
            "schema": {
                "name": data.table_schema.name,
                "columns": [
                    {
                        "name": col.name,
                        "type": col.type,
                        "nullable": col.nullable,
                        "primary_key": col.primary_key,
                        "foreign_key": col.foreign_key,
                    }
                    for col in data.table_schema.columns
                ],
                "indexes": data.table_schema.indexes,
                "foreign_keys": data.table_schema.foreign_keys,
            },
            "data": data.data,
            "metadata": {
                "extraction_timestamp": data.extraction_timestamp.isoformat(),
                "total_records": data.total_records,
                "custom_metadata": data.metadata,
            },
        }


# Main Service
class DataExtractionService:
    """
    Main service for dynamic data extraction and schema inspection.

    This service coordinates between inspectors, extractors, and serializers
    to provide a unified interface for data retrieval and processing.
    """

    def __init__(self, inspector: DataSourceInspector, extractor: DataExtractor, serializer: DataSerializer):
        self.inspector = inspector
        self.extractor = extractor
        self.serializer = serializer

    def get_available_tables(self) -> List[str]:
        """Get list of all available tables."""
        return self.inspector.get_table_names()

    def get_table_info(self, table_name: str) -> TableSchema:
        """Get detailed schema information for a table."""
        if not self.inspector.validate_table_exists(table_name):
            raise ValueError(f"Table '{table_name}' does not exist")

        return self.inspector.get_table_schema(table_name)

    def extract_table_data(
        self,
        table_name: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        include_schema: bool = True,
    ) -> ExtractedData:
        """
        Extract data from a table with optional filtering.

        Args:
            table_name: Name of the table to extract from
            filters: Optional filters to apply
            limit: Maximum number of records to extract
            include_schema: Whether to include schema information

        Returns:
            ExtractedData object containing the results
        """
        if not self.inspector.validate_table_exists(table_name):
            raise ValueError(f"Table '{table_name}' does not exist")

        # Get schema if requested
        schema = None
        if include_schema:
            schema = self.inspector.get_table_schema(table_name)

        # Extract data
        data = self.extractor.extract_table_data(table_name=table_name, filters=filters, limit=limit)

        return ExtractedData(table_name=table_name, table_schema=schema, data=data, total_records=len(data))

    def extract_user_data(self, context: UserDataContext) -> ExtractedData:
        """
        Extract data specific to a user.

        Args:
            context: User data context with filtering information

        Returns:
            ExtractedData object containing user-specific results
        """
        if not self.inspector.validate_table_exists(context.table_name):
            raise ValueError(f"Table '{context.table_name}' does not exist")

        # Get schema if requested
        schema = None
        if context.include_metadata:
            schema = self.inspector.get_table_schema(context.table_name)

        # Extract user-specific data
        data = self.extractor.extract_user_specific_data(context)

        return ExtractedData(
            table_name=context.table_name,
            table_schema=schema,
            data=data,
            total_records=len(data),
            metadata={"user_id": context.user_id, "filters": context.filters},
        )

    def serialize_for_vector_store(self, extracted_data: ExtractedData) -> Dict[str, Any]:
        """
        Serialize extracted data for vector store ingestion.

        Args:
            extracted_data: The data to serialize

        Returns:
            JSON-compatible dictionary
        """
        return self.serializer.serialize(extracted_data)

    def extract_and_serialize(
        self,
        table_name: str,
        user_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Convenience method to extract and serialize data in one call.

        Args:
            table_name: Name of the table to extract from
            user_id: Optional user ID for user-specific extraction
            filters: Optional filters to apply
            limit: Maximum number of records to extract

        Returns:
            Serialized data ready for vector store ingestion
        """
        if user_id:
            context = UserDataContext(user_id=user_id, table_name=table_name, filters=filters or {}, limit=limit)
            extracted_data = self.extract_user_data(context)
        else:
            extracted_data = self.extract_table_data(table_name=table_name, filters=filters, limit=limit)

        return self.serialize_for_vector_store(extracted_data)


# Factory Functions
def create_sql_extraction_service(engine: Engine) -> DataExtractionService:
    """Create a data extraction service for SQL databases."""
    inspector = SQLAlchemyInspector(engine)
    extractor = SQLAlchemyExtractor(engine)
    serializer = JSONDataSerializer()

    return DataExtractionService(inspector, extractor, serializer)


def create_extraction_service_from_config(config: Dict[str, Any]) -> DataExtractionService:
    """Create a data extraction service based on configuration."""
    source_type = config.get("source_type", "sql")

    if source_type == "sql":
        from app.database import engine

        return create_sql_extraction_service(engine)
    else:
        raise ValueError(f"Unsupported source type: {source_type}")

