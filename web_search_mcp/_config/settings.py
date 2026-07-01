"""Environment-based application settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for the web-search-mcp server.

    Configuration is loaded from environment variables.
    API keys are read directly (EXA_API_KEY).
    Other settings use the SEARCH_MCP_ prefix.

    """

    model_config = SettingsConfigDict(env_prefix="SEARCH_MCP_")

    user_agent: str = "web-search-mcp/1.0"
    rate_limit_search: int = 30
    rate_limit_fetch: int = 20
    exa_api_key: str = Field(default="", alias="EXA_API_KEY")


settings = Settings()
