"""Ollama integration module."""

from app.integrations.ollama.client import OllamaClient, OllamaClientError

__all__ = ["OllamaClient", "OllamaClientError"]
