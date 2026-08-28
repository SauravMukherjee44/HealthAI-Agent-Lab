from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HEALTHAI_", env_file=".env", extra="ignore")

    environment: str = "development"
    state_secret: str = "development-only-change-before-deploy"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    artifacts_dir: Path = ROOT / "backend" / "artifacts"
    max_audio_bytes: int = 2 * 1024 * 1024
    max_audio_seconds: int = 30
    max_image_bytes: int = 8 * 1024 * 1024
    voice_enabled: bool = False
    moonshine_cache_dir: Path | None = None
    moonshine_model_arch: int = 2
    orchestrator_backend: str = "auto"
    qwen_base_url: str = "http://127.0.0.1:12434/engines/v1"
    qwen_model: str = "huggingface.co/qwen/qwen3-0.6b-gguf:Q8_0"
    qwen_timeout_seconds: float = 45.0
    qwen_lambda_function: str | None = None
    quota_table: str | None = None
    rate_limit_enabled: bool = False
    triage_ttl_seconds: int = 60 * 60 * 24 * 7

    @property
    def origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
