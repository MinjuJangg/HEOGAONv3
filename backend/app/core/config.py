from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent

_load_env_file(PROJECT_ROOT / ".env")

DEFAULT_GMS_LLM_BASE_URL = "https://gms.ssafy.io/gmsapi/api.openai.com/v1"


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if not value:
        return default

    items = tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())
    return items or default


def _env_int(name: str, fallback_name: str, default: int | None = None) -> int | None:
    value = os.getenv(name) or os.getenv(fallback_name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _gms_reasoning_effort() -> str:
    value = os.getenv("LLM_REASONING_EFFORT", os.getenv("GMS_REASONING_EFFORT", "")).strip().lower()
    if value == "minimal":
        return "low"
    return value if value in {"none", "low", "medium", "high", "xhigh"} else ""


@dataclass(frozen=True)
class Settings:
    app_env: str
    enable_llm: bool
    enable_graph_rag: bool
    enable_demo_fallback: bool
    llm_provider: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_timeout_seconds: float
    llm_reasoning_effort: str
    llm_max_output_tokens: int | None
    graph_rag_base_url: str
    graph_rag_api_key: str
    graph_rag_timeout_seconds: float
    cors_allowed_origins: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_env=os.getenv("APP_ENV", "local"),
            enable_llm=_env_bool("ENABLE_LLM", True),
            enable_graph_rag=_env_bool("ENABLE_GRAPH_RAG", False),
            enable_demo_fallback=_env_bool("ENABLE_DEMO_FALLBACK", True),
            llm_provider=os.getenv("LLM_PROVIDER", "gms"),
            llm_api_key=os.getenv("LLM_API_KEY", os.getenv("GMS_API_KEY", os.getenv("GMS_KEY", ""))),
            llm_base_url=os.getenv("LLM_BASE_URL", os.getenv("GMS_BASE_URL", DEFAULT_GMS_LLM_BASE_URL)).rstrip("/"),
            llm_model=os.getenv("LLM_MODEL", os.getenv("GMS_MODEL", "gpt-5.5")),
            llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "12")),
            llm_reasoning_effort=_gms_reasoning_effort(),
            llm_max_output_tokens=_env_int("LLM_MAX_OUTPUT_TOKENS", "GMS_MAX_OUTPUT_TOKENS"),
            graph_rag_base_url=os.getenv("GRAPH_RAG_BASE_URL", "").rstrip("/"),
            graph_rag_api_key=os.getenv("GRAPH_RAG_API_KEY", ""),
            graph_rag_timeout_seconds=float(os.getenv("GRAPH_RAG_TIMEOUT_SECONDS", "8")),
            cors_allowed_origins=_env_csv(
                "CORS_ALLOWED_ORIGINS",
                (
                    "http://localhost:3100",
                    "http://127.0.0.1:3100",
                    "http://localhost:3101",
                    "http://127.0.0.1:3101",
                    "http://localhost:3102",
                    "http://127.0.0.1:3102",
                    "http://localhost:3103",
                    "http://127.0.0.1:3103",
                    "http://localhost:8792",
                    "http://127.0.0.1:8792",
                ),
            ),
        )

    @property
    def llm_available(self) -> bool:
        return self.enable_llm and bool(self.llm_api_key)

    @property
    def graph_rag_available(self) -> bool:
        return self.enable_graph_rag and bool(self.graph_rag_base_url)


settings = Settings.from_env()
