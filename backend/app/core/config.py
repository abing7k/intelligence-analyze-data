from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


ApiStyle = Literal["auto", "chat", "responses"]


class LLMModelConfig(BaseModel):
    id: str
    label: str
    provider: str
    model: str
    api_key: SecretStr | None
    base_url: str
    api_style: ApiStyle = "auto"
    is_default: bool = False

    @property
    def api_key_value(self) -> str | None:
        if self.api_key is None:
            return None
        return self.api_key.get_secret_value()

    @property
    def normalized_base_url(self) -> str:
        return normalize_openai_base_url(self.base_url)

    def public_dict(self) -> dict[str, str | bool]:
        return {
            "id": self.id,
            "label": self.label,
            "provider": self.provider,
            "model": self.model,
            "api_style": self.api_style,
            "is_default": self.is_default,
        }


class Settings(BaseSettings):
    app_env: str = "development"
    app_version: str = "0.1.0"

    provider: str = Field(default="openai", validation_alias="PROVIDER")
    api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "API_KEY"),
    )
    base_url: str = Field(
        default="http://144.22.219.57:10001/v1",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "BASE_URL"),
    )
    default_model: str = Field(
        default="gpt-5.5",
        validation_alias=AliasChoices("OPENAI_MODEL", "DEFAULT_MODEL"),
    )
    openai_timeout_seconds: int = 60
    openai_max_retries: int = 2
    openai_reasoning_effort: str = "medium"

    default_model_id: str = "gpt-5.5"

    model_1_id: str | None = "gpt-5.5"
    model_1_label: str | None = "GPT-5.5"
    model_1_provider: str | None = "sub2api-primary"
    model_1_model: str | None = "gpt-5.5"
    model_1_api_key: SecretStr | None = None
    model_1_base_url: str | None = "http://144.22.219.57:10001/v1"
    model_1_api_style: ApiStyle = "chat"

    model_2_id: str | None = "gpt-5.5-backup"
    model_2_label: str | None = "GPT-5.5 Backup"
    model_2_provider: str | None = "api-866646-backup"
    model_2_model: str | None = "gpt-5.5"
    model_2_api_key: SecretStr | None = None
    model_2_base_url: str | None = "https://api.866646.xyz/v1"
    model_2_api_style: ApiStyle = "chat"

    database_path: str = "backend/storage/app.sqlite3"
    upload_dir: str = "backend/storage/uploads"
    chart_dir: str = "backend/storage/charts"
    report_dir: str = "backend/storage/reports"
    max_upload_mb: int = 25
    execution_timeout_seconds: int = 12
    allow_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173"
    )

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def openai_api_key(self) -> str | None:
        if self.api_key is None:
            return None
        return self.api_key.get_secret_value()

    @property
    def openai_base_url(self) -> str:
        return normalize_openai_base_url(self.base_url)

    @property
    def llm_models(self) -> list[LLMModelConfig]:
        configured: list[LLMModelConfig] = []
        for index in (1, 2):
            model_id = getattr(self, f"model_{index}_id")
            model_name = getattr(self, f"model_{index}_model")
            base_url = getattr(self, f"model_{index}_base_url")
            if not model_id or not model_name or not base_url:
                continue
            api_key = getattr(self, f"model_{index}_api_key") or self.api_key
            configured.append(
                LLMModelConfig(
                    id=model_id,
                    label=getattr(self, f"model_{index}_label") or model_id,
                    provider=getattr(self, f"model_{index}_provider") or self.provider,
                    model=model_name,
                    api_key=api_key,
                    base_url=base_url,
                    api_style=getattr(self, f"model_{index}_api_style") or "auto",
                    is_default=model_id == self.default_model_id,
                )
            )

        if not configured:
            configured.append(
                LLMModelConfig(
                    id=self.default_model,
                    label=self.default_model,
                    provider=self.provider,
                    model=self.default_model,
                    api_key=self.api_key,
                    base_url=self.base_url,
                    api_style="auto",
                    is_default=True,
                )
            )
        if not any(model.is_default for model in configured):
            configured[0].is_default = True
        return configured

    @property
    def llm_model_ids(self) -> set[str]:
        return {model.id for model in self.llm_models} | {model.model for model in self.llm_models}

    @property
    def default_llm_model(self) -> LLMModelConfig:
        for model in self.llm_models:
            if model.is_default:
                return model
        return self.llm_models[0]

    def resolve_llm_model(self, model_id: str | None = None) -> LLMModelConfig:
        requested = (model_id or "").strip()
        if not requested:
            return self.default_llm_model
        for model in self.llm_models:
            if requested in {model.id, model.model}:
                return model
        from app.core.errors import AppError

        raise AppError(
            code="MODEL_NOT_CONFIGURED",
            message=f"Model '{requested}' is not configured on the backend.",
            status_code=400,
            details={"available_model_ids": sorted(self.llm_model_ids)},
        )

    def resolve_llm_model_chain(self, model_id: str | None = None) -> list[LLMModelConfig]:
        selected_model = self.resolve_llm_model(model_id)
        return [model for model in self.llm_models if model.model == selected_model.model] or [selected_model]

    def public_llm_models(self) -> list[dict[str, str | bool]]:
        models: list[dict[str, str | bool]] = []
        seen: set[str] = set()
        default_model_name = self.default_llm_model.model
        for model in self.llm_models:
            if model.model in seen:
                continue
            seen.add(model.model)
            providers = [candidate.provider for candidate in self.llm_models if candidate.model == model.model]
            models.append(
                {
                    "id": model.model,
                    "label": model.label,
                    "provider": " -> ".join(providers),
                    "model": model.model,
                    "api_style": model.api_style,
                    "is_default": model.model == default_model_name,
                }
            )
        return models

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allow_origins.split(",") if origin.strip()]

    @property
    def supported_file_types(self) -> list[str]:
        return [".csv", ".xls", ".xlsx"]

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    @property
    def database_file(self) -> Path:
        return self.resolve_path(self.database_path)

    @property
    def upload_path(self) -> Path:
        return self.resolve_path(self.upload_dir)

    @property
    def chart_path(self) -> Path:
        return self.resolve_path(self.chart_dir)

    @property
    def report_path(self) -> Path:
        return self.resolve_path(self.report_dir)

    def ensure_runtime_dirs(self) -> None:
        self.database_file.parent.mkdir(parents=True, exist_ok=True)
        self.upload_path.mkdir(parents=True, exist_ok=True)
        self.chart_path.mkdir(parents=True, exist_ok=True)
        self.report_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_runtime_dirs()
    return settings


def normalize_openai_base_url(value: str) -> str:
    cleaned = value.rstrip("/")
    for suffix in ("/responses", "/chat/completions", "/completions"):
        if cleaned.endswith(suffix):
            return cleaned[: -len(suffix)]
    return cleaned
