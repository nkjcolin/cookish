import json

import pytest

from app.config import Settings
from app.credentials import APIKeyProvider, CredentialUnavailable, _read_secret

SECRET = "arn:aws:secretsmanager:ap-southeast-1:123456789012:secret:school-key"


def test_local_credentials_do_not_contact_aws() -> None:
    def no_aws(arn):
        pytest.fail("Local credentials must not call Secrets Manager")

    assert APIKeyProvider(Settings(api_key="local-key"), secret_loader=no_aws).get() == "local-key"


def test_secret_is_cached_and_refreshed_after_rotation() -> None:
    now = [0.0]
    requests = []

    def load(arn):
        requests.append(arn)
        return f"key-{len(requests)}"

    provider = APIKeyProvider(Settings(secret_arn=SECRET), secret_loader=load, clock=lambda: now[0])
    assert provider.get() == "key-1"
    now[0] = 299
    assert provider.get() == "key-1"
    now[0] = 300
    assert provider.get() == "key-2"
    assert requests == [SECRET, SECRET]


@pytest.mark.parametrize(
    "value", ["raw-key", json.dumps({"SOCLAAS_API_KEY": "raw-key"}), '{"api_key":"raw-key"}']
)
def test_aws_secret_formats_without_network(monkeypatch, value) -> None:
    import boto3

    class SecretClient:
        def get_secret_value(self, *, SecretId):
            assert SecretId == SECRET
            return {"SecretString": value}

        def close(self):
            pass

    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: SecretClient())
    assert _read_secret(SECRET) == "raw-key"


@pytest.mark.parametrize("value", ["", "{broken", '{"unexpected":"private-value"}'])
def test_unusable_secret_is_not_exposed(monkeypatch, value) -> None:
    import boto3

    class SecretClient:
        def get_secret_value(self, **kwargs):
            return {"SecretString": value}

        def close(self):
            pass

    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: SecretClient())
    with pytest.raises(CredentialUnavailable) as exc:
        _read_secret(SECRET)
    assert "private-value" not in str(exc.value)
