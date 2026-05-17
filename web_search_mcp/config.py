from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for the web-search-mcp server.

    Configuration is loaded from environment variables with the SEARCH_MCP_ prefix.

    Attributes:
        weather_api_base: Base URL for the OpenMeteo weather API.
        user_agent: User agent string used for outgoing HTTP requests.
        rate_limit_search: Maximum search requests per minute.
        rate_limit_fetch: Maximum page fetch requests per minute.
    """

    model_config = SettingsConfigDict(env_prefix="SEARCH_MCP_")

    weather_api_base: str = "https://api.open-meteo.com/v1"
    user_agent: str = "web-search-mcp/1.0"
    rate_limit_search: int = 30
    rate_limit_fetch: int = 20


settings = Settings()
