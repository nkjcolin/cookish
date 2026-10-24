import pytest

from app.config import ConfigurationError, Settings
from app.errors import ApiError
from app.model_client import FakeModelClient, get_client


@pytest.fixture
def school_env() -> dict[str, str]:
    return {
        "AI_PROVIDER": "soclaas",
        "SOCLAAS_BASE_URL": "https://school.example/api/v1",
        "SOCLAAS_MODEL": "default-model",
        "SOCLAAS_API_KEY": "test-private-key",
    }


def test_fake_needs_no_school_or_aws_settings() -> None:
    assert Settings.from_env({}) == Settings()
    assert isinstance(get_client(), FakeModelClient)


def test_task_overrides_and_default_fallback(school_env) -> None:
    settings = Settings.from_env(school_env)
    assert settings.base_url == "https://school.example/api/v1/"
    assert settings.timeout_seconds == 20
    for task in ["receipt", "photo", "items", "interpret"]:
        assert settings.model_for_task(task) == "default-model"
    settings = Settings.from_env(
        {
            **school_env,
            "SOCLAAS_IMAGE_MODEL": "vision-model",
            "SOCLAAS_TEXT_MODEL": "list-model",
            "SOCLAAS_INTERPRET_MODEL": "adjust-model",
        }
    )
    assert settings.model_for_task("receipt") == "vision-model"
    assert settings.model_for_task("photo") == "vision-model"
    assert settings.model_for_task("items") == "list-model"
    assert settings.model_for_task("interpret") == "adjust-model"


def test_credentials_are_not_in_settings_repr(school_env) -> None:
    assert school_env["SOCLAAS_API_KEY"] not in repr(Settings.from_env(school_env))


def test_docker_env_file_quoted_values_match_unquoted_values(school_env) -> None:
    quoted = {name: f'"{value}"' for name, value in school_env.items()}
    assert Settings.from_env(quoted) == Settings.from_env(school_env)


@pytest.mark.parametrize("missing", ["SOCLAAS_BASE_URL", "SOCLAAS_MODEL", "SOCLAAS_API_KEY"])
def test_required_school_settings(school_env, missing) -> None:
    school_env.pop(missing)
    with pytest.raises(ConfigurationError):
        Settings.from_env(school_env)


@pytest.mark.parametrize(
    "url",
    [
        "http://school.example/v1",
        "https://user:private-value@school.example/v1",
        "https://school.example/v1?api_key=private-value",
        "https://school.example/v1#private-value",
        "https://school.example/v1/chat/completions",
        "https://school.example:invalid/v1",
        "not-a-url",
    ],
)
def test_bad_urls_are_rejected_without_echoing_them(school_env, url) -> None:
    school_env["SOCLAAS_BASE_URL"] = url
    with pytest.raises(ConfigurationError) as exc:
        Settings.from_env(school_env)
    assert "private-value" not in str(exc.value)


def test_local_http_is_available_for_mock_servers(school_env) -> None:
    school_env["SOCLAAS_BASE_URL"] = "http://127.0.0.1:9999/v1/"
    assert Settings.from_env(school_env).base_url == school_env["SOCLAAS_BASE_URL"]


def test_secret_reference_instead_of_a_local_key(school_env) -> None:
    school_env.pop("SOCLAAS_API_KEY")
    school_env["SOCLAAS_API_KEY_SECRET_ARN"] = (
        "arn:aws:secretsmanager:ap-southeast-1:123456789012:secret:school-key"
    )
    assert Settings.from_env(school_env).secret_arn is not None
    school_env["SOCLAAS_API_KEY"] = "another-private-key"
    with pytest.raises(ConfigurationError, match="exactly one"):
        Settings.from_env(school_env)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("AI_PROVIDER", "unknown"),
        ("SOCLAAS_OUTPUT_MODE", "unsupported"),
        ("SOCLAAS_MAX_OUTPUT_TOKENS", "invalid"),
        ("SOCLAAS_MAX_OUTPUT_TOKENS", "0"),
        ("SOCLAAS_MAX_OUTPUT_TOKENS", "999999"),
        ("SOCLAAS_API_KEY", "private\nvalue"),
        ("SOCLAAS_TIMEOUT_SECONDS", "invalid"),
        ("SOCLAAS_TIMEOUT_SECONDS", "0"),
        ("SOCLAAS_TIMEOUT_SECONDS", "nan"),
        ("SOCLAAS_TIMEOUT_SECONDS", "inf"),
        ("SOCLAAS_TIMEOUT_SECONDS", "121"),
    ],
)
def test_invalid_settings_fail_locally(school_env, name, value) -> None:
    with pytest.raises(ConfigurationError):
        Settings.from_env({**school_env, name: value})


def test_bad_runtime_configuration_is_a_safe_api_error(monkeypatch, caplog) -> None:
    monkeypatch.setenv("AI_PROVIDER", "soclaas")
    monkeypatch.setenv("SOCLAAS_API_KEY", "private-key-that-must-not-be-logged")
    with pytest.raises(ApiError) as exc:
        get_client()
    assert exc.value.code == "UPSTREAM_UNAVAILABLE"
    assert "private-key-that-must-not-be-logged" not in caplog.text


def test_explicit_local_timeout_override(school_env) -> None:
    assert Settings.from_env({**school_env, "SOCLAAS_TIMEOUT_SECONDS": "60"}).timeout_seconds == 60
