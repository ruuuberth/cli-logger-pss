from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "PixelStarships Logger"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "sqlite:///./pss_logger.db"
    
    # CORS
    ALLOWED_HOSTS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # PixelStarships API
    PSS_API_BASE_URL: str = "https://api.pixelstarships.com"
    
    class Config:
        env_file = ".env"

settings = Settings()