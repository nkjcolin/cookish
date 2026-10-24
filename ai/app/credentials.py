"""Retrieve school credentials without importing the experimental script."""

import json
import time
from collections.abc import Callable
from threading import Lock

from app.config import Settings


class CredentialUnavailable(Exception):
    pass


def _read_secret(arn: str) -> str:
    # Lazy import: fake and local-key requests never initialize an AWS client.
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        client = boto3.client(
            "secretsmanager",
            region_name=arn.split(":")[3],
            config=Config(connect_timeout=2, read_timeout=3, retries={"max_attempts": 0}),
        )
        response = client.get_secret_value(SecretId=arn)
        value = response.get("SecretString")
        if not isinstance(value, str):
            raise ValueError("A text secret is required")
        if value.lstrip().startswith("{"):
            data = json.loads(value)
            value = data.get("SOCLAAS_API_KEY") or data.get("api_key")
        if not isinstance(value, str) or not value.strip():
            raise ValueError("An API key is required")
        return value.strip()
    except (BotoCoreError, ClientError, ValueError, TypeError, AttributeError):
        raise CredentialUnavailable("The school API credential is unavailable") from None
    finally:
        if "client" in locals():
            client.close()


class APIKeyProvider:
    """Cache an AWS key for five minutes, with refresh support for rotation."""

    def __init__(
        self,
        settings: Settings,
        *,
        secret_loader: Callable[[str], str] = _read_secret,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._load = secret_loader
        self._clock = clock
        self._key: str | None = None
        self._expires = 0.0
        self._lock = Lock()

    def get(self) -> str:
        if self._settings.api_key:
            return self._settings.api_key
        if not self._settings.secret_arn:
            raise CredentialUnavailable("The school API credential is unavailable")
        with self._lock:
            if self._key is None or self._clock() >= self._expires:
                key = self._load(self._settings.secret_arn)
                if not key or not key.isascii() or "\n" in key or "\r" in key:
                    raise CredentialUnavailable("The school API credential is unavailable")
                self._key = key
                self._expires = self._clock() + 300
            return self._key
