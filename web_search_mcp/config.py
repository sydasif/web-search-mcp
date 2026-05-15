from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SEARCH_MCP_")

    weather_api_base: str = "https://api.open-meteo.com/v1"
    user_agent: str = "web-search-mcp/1.0"
    rate_limit_search: int = 30
    rate_limit_fetch: int = 20


settings = Settings()
