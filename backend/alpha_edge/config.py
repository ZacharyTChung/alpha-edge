from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://alpha:alpha@localhost:5432/alpha_edge"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    kalshi_api_key: str | None = None
    kalshi_api_secret: str | None = None
    polymarket_api_base: str = "https://gamma-api.polymarket.com"

    nba_stats_user_agent: str = "AlphaEdge/0.1"
    rotowire_feed_url: str | None = None

    twitter_bearer_token: str | None = None
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str = "AlphaEdge/0.1"

    alert_webhook_default_url: str | None = None

    anthropic_api_key: str | None = None
    anthropic_sentiment_model: str = "claude-sonnet-4-6"
    llm_min_liquidity: float = 1000.0  # skip LLM classification on illiquid markets


@lru_cache
def get_settings() -> Settings:
    return Settings()
