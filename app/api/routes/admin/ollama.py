"""
Ollama Admin Endpoints.

Public endpoints for querying available Ollama models and their types.
Automatically classifies models as LLM or embedding based on model family and name.
"""

import logging
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================


class OllamaModelInfo(BaseModel):
    """Information about a single Ollama model."""

    name: str = Field(..., description="Model name with tag (e.g., 'llama3.1:latest')")
    model: str = Field(..., description="Model identifier")
    family: str = Field(..., description="Model family (e.g., 'llama', 'bert')")
    families: list[str] = Field(
        default_factory=list, description="All model families"
    )
    parameter_size: str = Field(..., description="Model size (e.g., '8.0B', '137M')")
    quantization_level: str = Field(
        ..., description="Quantization level (e.g., 'Q4_K_M', 'F16')"
    )
    size_bytes: int = Field(..., description="Model size in bytes")
    model_type: Literal["llm", "embedding"] = Field(
        ..., description="Classification: 'llm' or 'embedding'"
    )
    modified_at: str = Field(..., description="Last modification timestamp")


class OllamaModelsResponse(BaseModel):
    """Response containing all available Ollama models."""

    models: list[OllamaModelInfo] = Field(..., description="List of available models")
    total: int = Field(..., description="Total number of models")
    llm_count: int = Field(..., description="Number of LLM models")
    embedding_count: int = Field(..., description="Number of embedding models")
    ollama_url: str = Field(..., description="Ollama API URL used")


class OllamaHealthResponse(BaseModel):
    """Ollama service health status."""

    status: Literal["healthy", "unhealthy"] = Field(
        ..., description="Service status"
    )
    ollama_url: str = Field(..., description="Ollama API URL")
    model_count: int | None = Field(None, description="Number of models available")
    error: str | None = Field(None, description="Error message if unhealthy")


# =============================================================================
# Helper Functions
# =============================================================================


def classify_model_type(model_data: dict) -> Literal["llm", "embedding"]:
    """
    Classify a model as LLM or embedding based on family and name.

    Classification rules (in order):
    1. If family contains 'bert' -> embedding
    2. If name contains 'embed' -> embedding
    3. Otherwise -> llm

    Args:
        model_data: Model data from Ollama /api/tags response

    Returns:
        'llm' or 'embedding'
    """
    name = model_data.get("name", "").lower()
    details = model_data.get("details", {})
    family = details.get("family", "").lower()
    families = [f.lower() for f in details.get("families", [])]

    # Rule 1: bert family indicates embedding model
    if "bert" in family or any("bert" in f for f in families):
        return "embedding"

    # Rule 2: name contains "embed" indicates embedding model
    if "embed" in name:
        return "embedding"

    # Default: LLM
    return "llm"


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/models", response_model=OllamaModelsResponse)
async def list_ollama_models(
    model_type: Literal["llm", "embedding"] | None = Query(
        None, description="Filter by model type"
    ),
):
    """
    List all available models in Ollama.

    Automatically classifies each model as:
    - **llm**: Language models (llama, qwen, deepseek, etc.)
    - **embedding**: Embedding models (nomic-embed, bge-m3, mxbai-embed, etc.)

    Classification is based on model family (bert = embedding) and name (contains 'embed').

    Args:
        model_type: Optional filter to return only 'llm' or 'embedding' models

    Returns:
        List of models with classification and aggregated counts
    """
    settings = get_settings()
    ollama_url = settings.OLLAMA_API_URL

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ollama_url}/api/tags",
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

    except httpx.ConnectError as e:
        logger.error(f"Failed to connect to Ollama at {ollama_url}: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Ollama service at {ollama_url}",
        ) from e
    except httpx.HTTPStatusError as e:
        logger.error(f"Ollama API error: {e}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Ollama API error: {e.response.text}",
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error querying Ollama: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error querying Ollama: {e!s}",
        ) from e

    # Process models
    models: list[OllamaModelInfo] = []
    for m in data.get("models", []):
        details = m.get("details", {})
        classified_type = classify_model_type(m)

        model_info = OllamaModelInfo(
            name=m.get("name", ""),
            model=m.get("model", ""),
            family=details.get("family", "unknown"),
            families=details.get("families", []),
            parameter_size=details.get("parameter_size", "unknown"),
            quantization_level=details.get("quantization_level", "unknown"),
            size_bytes=m.get("size", 0),
            model_type=classified_type,
            modified_at=m.get("modified_at", ""),
        )
        models.append(model_info)

    # Apply filter if specified
    if model_type:
        models = [m for m in models if m.model_type == model_type]

    # Sort: LLMs first, then embeddings, alphabetically within each group
    models.sort(key=lambda x: (x.model_type == "embedding", x.name))

    # Calculate counts (before filtering for accurate totals)
    all_models = data.get("models", [])
    llm_count = sum(1 for m in all_models if classify_model_type(m) == "llm")
    embedding_count = len(all_models) - llm_count

    return OllamaModelsResponse(
        models=models,
        total=len(models),
        llm_count=llm_count if not model_type else (len(models) if model_type == "llm" else 0),
        embedding_count=embedding_count if not model_type else (len(models) if model_type == "embedding" else 0),
        ollama_url=ollama_url,
    )


@router.get("/health", response_model=OllamaHealthResponse)
async def ollama_health_check():
    """
    Check Ollama service health.

    Returns:
        Health status including availability and model count
    """
    settings = get_settings()
    ollama_url = settings.OLLAMA_API_URL

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ollama_url}/api/tags",
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()

        model_count = len(data.get("models", []))

        return OllamaHealthResponse(
            status="healthy",
            ollama_url=ollama_url,
            model_count=model_count,
            error=None,
        )

    except httpx.ConnectError as e:
        return OllamaHealthResponse(
            status="unhealthy",
            ollama_url=ollama_url,
            model_count=None,
            error=f"Connection failed: {e!s}",
        )
    except Exception as e:
        return OllamaHealthResponse(
            status="unhealthy",
            ollama_url=ollama_url,
            model_count=None,
            error=str(e),
        )


__all__ = [
    "router",
    "OllamaModelInfo",
    "OllamaModelsResponse",
    "OllamaHealthResponse",
]
