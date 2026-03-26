"""Application configuration via environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration. All values come from env vars or .env file."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Environment
    environment: str = "development"

    # AWS Bedrock
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_profile: str | None = None

    # LLM Models — tiered for cost/quality tradeoffs
    # Analysis model: main workhorse for code analysis and doc generation
    llm_analysis_model: str = "us.anthropic.claude-sonnet-4-20250514"
    # Heavy model: architecture-level synthesis, complex legacy code
    llm_heavy_model: str = "us.anthropic.claude-opus-4-20250514"
    # Fast model: classification, metadata extraction, summaries
    llm_fast_model: str = "us.anthropic.claude-haiku-4-5-20251001"

    # Embeddings
    embedding_model: str = "cohere.embed-english-v3"
    embedding_dimensions: int = 1024

    # Database
    database_url: str = "postgresql+asyncpg://wiki:wiki_dev_password@localhost:5432/wiki_engine"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # Git
    git_clone_dir: Path = Path("/tmp/wiki-engine/repos")

    # Pipeline tuning
    max_files_per_page_context: int = 15
    max_tokens_per_llm_call: int = 180_000
    wiki_pages_target: int = 12  # 8-12 pages per wiki
    diagrams_per_page_min: int = 3
    citations_per_page_min: int = 5


settings = Settings()
