from pydantic import BaseModel, Field


class SupervisorConfig(BaseModel):
    """
    Configuración para el Supervisor Agent.

    Incluye configuración para:
    - Control de flujo conversacional
    - LLM Response Analysis (COMPLEX model - gemma2)
    - Umbrales de calidad
    - Escalada a humanos

    Performance-optimized defaults (2026-01 update):
    - Uses COMPLEX model instead of REASONING (~10s vs ~100s)
    - Lower skip_threshold (0.90) for faster responses
    - Balanced weights (50/50) for heuristic/LLM
    - Shorter timeout (15s) with asyncio.wait_for protection
    """

    # Control de flujo
    max_agent_switches: int = 3  # Reduced from 5 to prevent excessive loops
    conversation_timeout: int = 1800  # 30 minutos
    enable_handoff_detection: bool = True

    # Quality thresholds
    quality_threshold: float = Field(
        default=0.65,  # Lowered from 0.7 to accept more responses
        ge=0.0,
        le=1.0,
        description="Minimum quality score to accept a response",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        le=5,  # Reduced max from 10 to 5
        description="Maximum retry attempts before accepting response",
    )
    enable_human_handoff: bool = Field(
        default=True,
        description="Enable automatic escalation to human agents",
    )
    enable_re_routing: bool = Field(
        default=True,
        description="Enable re-routing to different agents on low quality",
    )
    enable_response_enhancement: bool = Field(
        default=False,
        description="Enable LLM-based response enhancement (slow)",
    )

    # LLM Response Analysis configuration (PERFORMANCE OPTIMIZED)
    enable_llm_analysis: bool = Field(
        default=True,
        description="Enable LLM analysis using COMPLEX model (gemma2)",
    )
    llm_analysis_timeout: int = Field(
        default=15,  # Reduced from 30 - COMPLEX model is faster
        ge=5,
        le=60,  # Reduced max from 120 to 60
        description="Timeout in seconds for LLM analysis",
    )
    skip_llm_threshold: float = Field(
        default=0.90,  # Reduced from 0.95 for more aggressive skipping
        ge=0.0,
        le=1.0,
        description="Skip LLM analysis if heuristic score >= this value",
    )
    llm_weight: float = Field(
        default=0.5,  # Changed from 0.6 to 0.5 for balanced scoring
        ge=0.0,
        le=1.0,
        description="Weight of LLM score in combined evaluation (0.5 = 50%)",
    )

    # Quality sub-thresholds
    completeness_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum completeness score",
    )
    relevance_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score",
    )
    task_completion_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum task completion score",
    )
