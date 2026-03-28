from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    neoantigen_database_url: str = ""
    neoantigen_learnings_db: str = "agent/learnings/learnings.db"
    neoantigen_approval_secret: str = ""
    neoantigen_signed_url_ttl_seconds: int = 900
    neoantigen_phase2_mirror_outputs: bool = False
    neoantigen_image_digest: str = "sha256:latest"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
