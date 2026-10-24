"""Server-owned provider settings. No file loading or network calls on import."""

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Self
from urllib.parse import urlsplit

TIMEOUT_SECONDS = 20


class ConfigurationError(ValueError):
    """Messages identify settings, never their secret values."""


@dataclass(frozen=True)
class Settings:
    provider: str = "fake"
    base_url: str = ""
    model: str = ""
    api_key: str | None = field(default=None, repr=False)
    secret_arn: str | None = field(default=None, repr=False)
    image_model: str | None = None
    text_model: str | None = None
    interpret_model: str | None = None
    output_mode: str = "json_schema"
    max_output_tokens: int = 4096
    timeout_seconds: float = TIMEOUT_SECONDS

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Self:
        env = os.environ if environ is None else environ

        def read(name: str) -> str:
            value = env.get(name, "").strip()
            # Docker --env-file keeps wrapping quotes; uv/dotenv-style loaders do not.
            if len(value) >= 2 and value[0] in {"'", '"'} and value[-1] == value[0]:
                value = value[1:-1].strip()
            return value

        provider = read("AI_PROVIDER") or "fake"
        if provider == "fake":
            return cls()
        if provider != "soclaas":
            raise ConfigurationError("AI_PROVIDER must be fake or soclaas")

        base_url = read("SOCLAAS_BASE_URL")
        model = read("SOCLAAS_MODEL")
        if not base_url or not model:
            raise ConfigurationError("SOCLAAS_BASE_URL and SOCLAAS_MODEL are required")
        try:
            url = urlsplit(base_url)
            local = url.hostname in {"localhost", "127.0.0.1", "::1"}
            valid = url.scheme == "https" or (url.scheme == "http" and local)
            valid = valid and bool(url.hostname) and bool(url.port is None or url.port > 0)
        except ValueError:
            valid = False
        if not valid or url.username or url.password or url.query or url.fragment:
            raise ConfigurationError("SOCLAAS_BASE_URL must be a credential-free HTTPS base URL")
        if url.path.rstrip("/").endswith("/chat/completions"):
            raise ConfigurationError("SOCLAAS_BASE_URL must not include /chat/completions")

        api_key = read("SOCLAAS_API_KEY") or None
        secret_arn = read("SOCLAAS_API_KEY_SECRET_ARN") or None
        if bool(api_key) == bool(secret_arn):
            raise ConfigurationError(
                "Set exactly one of SOCLAAS_API_KEY or SOCLAAS_API_KEY_SECRET_ARN"
            )
        if api_key and (not api_key.isascii() or "\n" in api_key or "\r" in api_key):
            raise ConfigurationError("SOCLAAS_API_KEY must be a single-line ASCII credential")
        if secret_arn:
            parts = secret_arn.split(":", 5)
            if (
                len(parts) != 6
                or parts[0] != "arn"
                or parts[2] != "secretsmanager"
                or not parts[3]
                or not parts[4]
                or not parts[5].startswith("secret:")
            ):
                raise ConfigurationError("SOCLAAS_API_KEY_SECRET_ARN must identify a secret")
        output_mode = read("SOCLAAS_OUTPUT_MODE") or "json_schema"
        if output_mode not in {"json_schema", "json_object"}:
            raise ConfigurationError("SOCLAAS_OUTPUT_MODE must be json_schema or json_object")
        try:
            max_output_tokens = int(read("SOCLAAS_MAX_OUTPUT_TOKENS") or "4096")
        except ValueError:
            raise ConfigurationError("SOCLAAS_MAX_OUTPUT_TOKENS must be an integer") from None
        if not 1 <= max_output_tokens <= 16384:
            raise ConfigurationError("SOCLAAS_MAX_OUTPUT_TOKENS must be between 1 and 16384")
        try:
            timeout_seconds = float(read("SOCLAAS_TIMEOUT_SECONDS") or str(TIMEOUT_SECONDS))
        except ValueError:
            raise ConfigurationError("SOCLAAS_TIMEOUT_SECONDS must be a number") from None
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120:
            raise ConfigurationError(
                "SOCLAAS_TIMEOUT_SECONDS must be greater than 0 and at most 120"
            )
        return cls(
            provider=provider,
            base_url=base_url.rstrip("/") + "/",
            model=model,
            api_key=api_key,
            secret_arn=secret_arn,
            image_model=read("SOCLAAS_IMAGE_MODEL") or None,
            text_model=read("SOCLAAS_TEXT_MODEL") or None,
            interpret_model=read("SOCLAAS_INTERPRET_MODEL") or None,
            output_mode=output_mode,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
        )

    def model_for_task(self, task: str) -> str:
        if task in {"receipt", "photo"}:
            return self.image_model or self.model
        if task == "items":
            return self.text_model or self.model
        if task == "interpret":
            return self.interpret_model or self.model
        raise ValueError("Unknown model task")
