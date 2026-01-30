from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    weather_api_base: str = "https://api.open-meteo.com/v1"
    default_max_results: int = 5
    user_agent: str = "web-search-mcp/1.0"

    class Config:
        env_prefix = "SEARCH_MCP_"


settings = Settings()
