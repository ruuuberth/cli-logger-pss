from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, DotEnvSettingsSource, EnvSettingsSource, PydanticBaseSettingsSource
from typing import List


class CsvEnvSettingsSource(EnvSettingsSource):
    def prepare_field_value(self, field_name: str, field: FieldInfo, value, value_is_complex: bool):
        if field_name == "ALLOWED_HOSTS" and isinstance(value, str):
            cleaned_value = value.strip()
            if not cleaned_value:
                return []
            if cleaned_value.startswith("["):
                return super().prepare_field_value(field_name, field, value, value_is_complex)
            return [host.strip() for host in cleaned_value.split(",") if host.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class CsvDotEnvSettingsSource(DotEnvSettingsSource):
    def prepare_field_value(self, field_name: str, field: FieldInfo, value, value_is_complex: bool):
        if field_name == "ALLOWED_HOSTS" and isinstance(value, str):
            cleaned_value = value.strip()
            if not cleaned_value:
                return []
            if cleaned_value.startswith("["):
                return super().prepare_field_value(field_name, field, value, value_is_complex)
            return [host.strip() for host in cleaned_value.split(",") if host.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    PROJECT_NAME: str = "PixelStarships Logger"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "sqlite:///./pss_logger.db"
    
    # CORS
    ALLOWED_HOSTS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    
    # PixelStarships API
    PSS_API_BASE_URL: str = "https://api.pixelstarships.com"
    DESIGNS_CACHE_TTL_SECONDS: int = 86400
    BATTLE_REPORT_CACHE_TTL_SECONDS: int = 3600
    PSS_CHECKSUM_KEY: str = ""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        return (
            init_settings,
            CsvEnvSettingsSource(settings_cls),
            CsvDotEnvSettingsSource(settings_cls),
            file_secret_settings,
        )
    
    class Config:
        env_file = ".env"

settings = Settings()
