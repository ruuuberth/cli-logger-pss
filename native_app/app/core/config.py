from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, DotEnvSettingsSource, EnvSettingsSource, PydanticBaseSettingsSource
from typing import List


class CsvEnvSettingsSource(EnvSettingsSource):
    def prepare_field_value(self, field_name: str, field: FieldInfo, value, value_is_complex: bool):
        list_fields = {"ALLOWED_HOSTS", "API_FLOW_IGNORE_HOSTS"}
        if field_name in list_fields and isinstance(value, str):
            cleaned_value = value.strip()
            if not cleaned_value:
                return []
            if cleaned_value.startswith("["):
                return super().prepare_field_value(field_name, field, value, value_is_complex)
            return [host.strip() for host in cleaned_value.split(",") if host.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class CsvDotEnvSettingsSource(DotEnvSettingsSource):
    def prepare_field_value(self, field_name: str, field: FieldInfo, value, value_is_complex: bool):
        list_fields = {"ALLOWED_HOSTS", "API_FLOW_IGNORE_HOSTS"}
        if field_name in list_fields and isinstance(value, str):
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
    PSS_API_REQUEST_TIMEOUT_SECONDS: int = 20
    DESIGNS_CACHE_TTL_SECONDS: int = 86400
    ITEMS_API_CACHE_TTL_SECONDS: int = 86400
    BATTLE_REPORT_CACHE_TTL_SECONDS: int = 3600
    PSS_CHECKSUM_KEY: str = ""

    # API Flow capture (mitmproxy)
    API_FLOW_ENABLED: bool = True
    MITMPROXY_BINARY: str = "mitmdump"
    MITMPROXY_LISTEN_HOST: str = "127.0.0.1"
    MITMPROXY_LISTEN_PORT: int = 8081
    API_FLOW_BODY_MAX_CHARS: int = 4000
    API_FLOW_RETENTION_DAYS: int = 7
    API_FLOW_MAX_DB_MB: int = 512
    API_FLOW_CAPTURE_HTTPS: bool = True
    API_FLOW_IGNORE_HOSTS: List[str] = []

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
