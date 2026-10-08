import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
    postgres_uri: str = os.getenv(
        "POSTGRES_URI", "postgresql://logsense:logsense@postgres:5432/logsense"
    )
    redis_uri: str = os.getenv("REDIS_URI", "redis://redis:6379/0")
    model_path: str = os.getenv("MODEL_PATH", "")
    evaluations_dir: str = os.getenv("EVALUATIONS_DIR", "/evaluations")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "")
    api_key: str = os.getenv("LOGSENSE_API_KEY", "")
    review_threshold: float = float(os.getenv("REVIEW_THRESHOLD", "0.6"))


settings = Settings()
