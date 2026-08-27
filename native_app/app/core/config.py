import logging

from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from typing import List

logger = logging.getLogger(__name__)


_LIST_FIELDS = {
    "ALLOWED_HOSTS",
    "API_FLOW_IGNORE_HOSTS",
    "API_FLOW_CAPTURE_HOST_ALLOWLIST",
    "API_FLOW_CAPTURE_PATH_ALLOWLIST",
}


class _ListCompatMixin:
    _warned_fields: set[str] = set()

    def _prepare_list_field_value(self, field_name: str, field: FieldInfo, value, value_is_complex: bool):
        if field_name in _LIST_FIELDS and isinstance(value, str):
            cleaned_value = value.strip()
            if not cleaned_value:
                return []
            if cleaned_value.startswith("["):
                return super().prepare_field_value(field_name, field, value, value_is_complex)
            if field_name not in self._warned_fields:
                logger.warning(
                    "event=config_list_csv_deprecated field=%s message=%s",
                    field_name,
                    'Usa JSON array en .env, ejemplo: ["api.pixelstarships.com"]',
                )
                self._warned_fields.add(field_name)
            return [token.strip() for token in cleaned_value.split(",") if token.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class ListCompatEnvSettingsSource(_ListCompatMixin, EnvSettingsSource):
    def prepare_field_value(self, field_name: str, field: FieldInfo, value, value_is_complex: bool):
        return self._prepare_list_field_value(field_name, field, value, value_is_complex)


class ListCompatDotEnvSettingsSource(_ListCompatMixin, DotEnvSettingsSource):
    def prepare_field_value(self, field_name: str, field: FieldInfo, value, value_is_complex: bool):
        return self._prepare_list_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

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
    API_FLOW_IGNORE_HOSTS: List[str] = [
        "player-auth.services.api.unity.com",
        "config.services.api.unity.com",
        "config.uca.cloud.unity3d.com",
        "collect.analytics.unity3d.com",
        "perf-events.cloud.unity3d.com",
    ]
    API_FLOW_CAPTURE_HOST_ALLOWLIST: List[str] = ["api.pixelstarships.com"]
    API_FLOW_CAPTURE_PATH_ALLOWLIST: List[str] = ["/BattleService/GetBattle3"]

    # Reporting
    REPORT_ENABLE: bool = True
    REPORT_OUTPUT_DIR: str = "./native_app/reports"
    REPORT_DEFAULT_FORMAT: str = "excel"
    REPORT_INCLUDE_TIMESTAMP: bool = True
    REPORT_FILENAME_BASE: str = "Reporte_Batallas"

    # CLI behavior
    CLI_NONINTERACTIVE: bool = False
    CLI_FORCE_ASCII: bool = False

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./native_app/logs/native_app.log"

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
            ListCompatEnvSettingsSource(settings_cls),
            ListCompatDotEnvSettingsSource(settings_cls),
            file_secret_settings,
        )
    
settings = Settings()
