import os
from typing import Optional, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _coerce_bool(v: Any) -> bool:
    """Coerce env values like 'WARN', '1', 'true' to bool so Settings always loads."""
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    s = str(v).strip().upper()
    if s in ("1", "TRUE", "YES", "ON"):
        return True
    return False  # "WARN", "0", "FALSE", etc.


class Settings(BaseSettings):
    """Global configuration settings for Alpha-Omega."""
    
    # Project Info
    PROJECT_NAME: str = "Alpha-Omega System"
    VERSION: str = "0.1.0"
    DEBUG: bool = Field(default=False, description="Enable debug mode")

    @field_validator("DEBUG", mode="before")
    @classmethod
    def coerce_debug(cls, v: Any) -> bool:
        return _coerce_bool(v)

    # API Keys
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API Key")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, description="Anthropic API Key")
    GOOGLE_API_KEY: Optional[str] = Field(default=None, description="Google API Key")
    ALPACA_API_KEY: Optional[str] = Field(default=None, description="Alpaca API Key")
    ALPACA_SECRET_KEY: Optional[str] = Field(default=None, description="Alpaca Secret Key")
    BLOOMBERG_API_KEY: Optional[str] = Field(default=None, description="Bloomberg API Key")
    POLYGON_API_KEY: Optional[str] = Field(default=None, description="Polygon.io API Key")

    # Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    LOGS_DIR: str = os.path.join(BASE_DIR, "logs")

    # Ollama (local dev only — not used in production)
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", description="Ollama server URL (local dev only)")
    OLLAMA_MODEL: str = Field(default="llama3.2", description="Ollama model name (local dev only)")

    # Model Configuration
    DEFAULT_LLM_MODEL: str = "gemini-pro"
    FAST_LLM_MODEL: str = "gemini-pro"
    REASONING_LLM_MODEL: str = "claude-3-opus-20240229"

    # Risk Management
    MAX_DRAWDOWN_LIMIT: float = 0.15 # 15%
    CONFIDENCE_THRESHOLD: float = 0.85 # 85%

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8", 
        case_sensitive=True,
        extra="ignore"
    )

def get_settings() -> Settings:
    return Settings()

settings = get_settings()
