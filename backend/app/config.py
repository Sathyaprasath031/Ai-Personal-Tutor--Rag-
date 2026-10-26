from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    postgres_url: str = "postgresql://tutor:tutor@db:5432/tutor"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # File storage
    upload_dir: str = "/data/uploads"

    # Auth
    jwt_secret: str = "tutor-super-secret-jwt-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 1440  # 24 hours

    # Anthropic
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"
    rewrite_model: str = "claude-haiku-4-20250414"

    # OpenAI & Compatible Providers (Groq, OpenRouter, Ollama)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""

    # Groq (Free Tier)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Google Gemini API
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # Embedding & Reranking
    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384
    rerank_model: str = "BAAI/bge-reranker-base"

    # Chunking
    chunk_words: int = 500
    chunk_overlap_words: int = 60

    # Retrieval
    # bge-reranker-base maps logits to [0, 1] via sigmoid.
    # Irrelevant chunks score ~0.50 (logit ~0.0), while relevant chunks score >=0.65 (logit >=0.7).
    relevance_threshold: float = 0.58


settings = Settings()
