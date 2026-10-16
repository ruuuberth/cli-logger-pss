import logging
from typing import Any, List

from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    SettingsError,
)

logger = logging.getLogger(__name__)

# Contrato de valores de lista desde la eliminación del soporte CSV (#16):
# los campos tipo List solo aceptan JSON array. Un valor vacío (`FIELD=`) es
# inválido y falla al arrancar; para una lista vacía usar `FIELD=[]`.
_JSON_ARRAY_HINT = (
    'Usa formato JSON array en .env, p. ej. API_FLOW_IGNORE_HOSTS=["api.pixelstarships.com"]. '
    "Para una lista vacía usa FIELD=[] (p. ej. API_FLOW_IGNORE_HOSTS=[])."
)


def _raise_config_invalid(field_name: str, value: Any, exc: Exception) -> None:
    logger.error(
        "event=config_invalid field=%s hint=%s",
        field_name,
        _JSON_ARRAY_HINT,
        exc_info=True,
    )
    raise SettingsError(
        f"valor inválido para '{field_name}' ({value!r}): {_JSON_ARRAY_HINT}"
    ) from exc


class HintedEnvSettingsSource(EnvSettingsSource):
    """EnvSettingsSource con log + hint de migración al fallar un valor de lista."""

    def decode_complex_value(
        self, field_name: str, field: FieldInfo, value: Any
    ) -> Any:
        try:
            return super().decode_complex_value(field_name, field, value)
        except ValueError as exc:
            _raise_config_invalid(field_name, value, exc)


class HintedDotEnvSettingsSource(DotEnvSettingsSource):
    """DotEnvSettingsSource con log + hint de migración al fallar un valor de lista."""

    def decode_complex_value(
        self, field_name: str, field: FieldInfo, value: Any
    ) -> Any:
        try:
            return super().decode_complex_value(field_name, field, value)
        except ValueError as exc:
            _raise_config_invalid(field_name, value, exc)


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
    # Normalized replay history kept per player pair. 1 = legacy behavior
    # (only the newest battle's ships/rooms/crew per pair). Raise to give the
    # H2H fleet breakdown (#8) real usage history at a linear DB cost.
    API_FLOW_REPLAYS_PER_PAIR: int = 1
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
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            HintedEnvSettingsSource(settings_cls),
            HintedDotEnvSettingsSource(settings_cls),
            file_secret_settings,
        )


settings = Settings()
