"""
Pydantic models for prompt templates.

This module defines the data structures for prompt templates,
providing validation and type safety for the YAML-based prompt system.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class VariableType(str, Enum):
    """Supported variable types for prompt templates."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    ANY = "any"


class PromptVariable(BaseModel):
    """Definition of a variable that can be used in a prompt template."""

    name: str = Field(..., description="Variable name")
    type: VariableType = Field(default=VariableType.STRING, description="Variable type")
    required: bool = Field(default=True, description="Whether the variable is required")
    description: Optional[str] = Field(None, description="Variable description")
    default: Optional[Any] = Field(None, description="Default value if not provided")

    model_config = {"use_enum_values": True}


class PromptMetadata(BaseModel):
    """Metadata for prompt configuration."""

    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="LLM temperature")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens to generate")
    model: Optional[str] = Field(None, description="Preferred LLM model")
    language: Optional[str] = Field(default="es", description="Response language")
    domain: Optional[str] = Field(None, description="Business domain")
    agent: Optional[str] = Field(None, description="Target agent")
    tags: List[str] = Field(default_factory=list, description="Searchable tags")

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: Optional[float]) -> Optional[float]:
        """Validate temperature is within acceptable range."""
        if v is not None and not (0.0 <= v <= 2.0):
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v


class PromptTemplate(BaseModel):
    """
    A prompt template with metadata and variable definitions.

    Represents a single prompt that can be rendered with variables.
    """

    key: str = Field(..., description="Unique identifier for the prompt (e.g., 'ecommerce.product.search')")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="What this prompt does")
    version: str = Field(default="1.0.0", description="Semantic version")
    template: str = Field(..., description="Prompt template text with {variables}")
    metadata: PromptMetadata = Field(default_factory=PromptMetadata, description="Prompt configuration")
    variables: List[PromptVariable] = Field(default_factory=list, description="Variable definitions")

    @field_validator("key")
    @classmethod
    def validate_key_format(cls, v: str) -> str:
        """Validate key follows naming convention (domain.agent.action)."""
        parts = v.split(".")
        if len(parts) < 2:
            raise ValueError("Key must have at least 2 parts separated by dots (e.g., 'domain.action')")
        return v

    @field_validator("version")
    @classmethod
    def validate_version_format(cls, v: str) -> str:
        """Validate version follows semantic versioning."""
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError("Version must follow semantic versioning (e.g., '1.0.0')")
        try:
            [int(p) for p in parts]
        except ValueError:
            raise ValueError("Version parts must be integers")
        return v

    def get_required_variables(self) -> List[str]:
        """Get list of required variable names."""
        return [var.name for var in self.variables if var.required]

    def get_optional_variables(self) -> List[str]:
        """Get list of optional variable names."""
        return [var.name for var in self.variables if not var.required]

    def has_variable(self, name: str) -> bool:
        """Check if template has a specific variable."""
        return any(var.name == name for var in self.variables)


class PromptCollection(BaseModel):
    """Collection of related prompts from a YAML file."""

    prompts: List[PromptTemplate] = Field(..., description="List of prompt templates")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Collection-level metadata")

    def get_prompt(self, key: str) -> Optional[PromptTemplate]:
        """Get a prompt by key."""
        for prompt in self.prompts:
            if prompt.key == key:
                return prompt
        return None

    def get_prompts_by_domain(self, domain: str) -> List[PromptTemplate]:
        """Get all prompts for a specific domain."""
        return [p for p in self.prompts if p.metadata.domain == domain]

    def get_prompts_by_agent(self, agent: str) -> List[PromptTemplate]:
        """Get all prompts for a specific agent."""
        return [p for p in self.prompts if p.metadata.agent == agent]

    def get_prompts_by_tag(self, tag: str) -> List[PromptTemplate]:
        """Get all prompts with a specific tag."""
        return [p for p in self.prompts if tag in p.metadata.tags]


class PromptRenderContext(BaseModel):
    """Context for rendering a prompt template."""

    variables: Dict[str, Any] = Field(default_factory=dict, description="Variables to substitute")
    strict: bool = Field(default=True, description="Raise error on missing required variables")

    def add_variable(self, name: str, value: Any) -> None:
        """Add a variable to the context."""
        self.variables[name] = value

    def add_variables(self, **kwargs: Any) -> None:
        """Add multiple variables to the context."""
        self.variables.update(kwargs)
