from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class VectorDocument(BaseModel):
    content: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VectorQueryResult(BaseModel):
    content: Any
    metadata: Dict[str, Any]
    score: Optional[float] = None
    id: Optional[str] = None


class VectorDBConfig(BaseModel):
    user_id: str
    collection_name: Optional[str] = "user_data"
    distance_function: Optional[str] = "cosine"
    embedding_model: Optional[str] = "text-embedding-ada-002"
