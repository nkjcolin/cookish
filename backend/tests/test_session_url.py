"""Where the database is: DATABASE_URL, then the Secrets Manager secret, then local.

These need no database and no AWS: a fake stands in for the secret.
"""

import sys
import types

import pytest

from app.db import session

SECRET = {
    "username": "cookish_admin",
    "password": "p@ss:w/rd#?%",
    "host": "cookish.abc123.ap-southeast-1.rds.amazonaws.com",
    "port": 5432,
    "dbname": "cookish",
}


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in ("DATABASE_URL", "DB_SECRET_ARN", "DB_NAME", "DB_SSLMODE"):
        monkeypatch.delenv(name, raising=False)


def test_with_nothing_set_it_is_the_local_database():
    assert session.database_url() == session.LOCAL_URL


def test_database_url_wins_over_the_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://a:b@h/d")
    monkeypatch.setenv("DB_SECRET_ARN", "arn:aws:secretsmanager:ap-southeast-1:1:secret:x")
    monkeypatch.setattr(session, "_read_secret", lambda arn: pytest.fail("must not be read"))
    assert session.database_url() == "postgresql+psycopg://a:b@h/d"


def test_the_url_is_built_from_the_secret_whatever_the_password_holds(monkeypatch):
    monkeypatch.setenv("DB_SECRET_ARN", "arn:secret")
    monkeypatch.setattr(session, "_read_secret", lambda arn: SECRET)
    url = session.database_url()
    assert url.drivername == "postgresql+psycopg"
    assert (url.username, url.password) == ("cookish_admin", "p@ss:w/rd#?%")
    assert (url.host, url.port, url.database) == (SECRET["host"], 5432, "cookish")
    assert url.query == {"sslmode": "require"}
    # and it survives being written out and read back, which is what the engine does
    from sqlalchemy.engine import make_url

    again = make_url(url.render_as_string(hide_password=False))
    assert again.password == "p@ss:w/rd#?%"


def test_the_port_and_database_have_defaults(monkeypatch):
    secret = {k: v for k, v in SECRET.items() if k not in ("port", "dbname")}
    monkeypatch.setenv("DB_NAME", "cookish_prod")
    url = session.url_from_secret(secret)
    assert (url.port, url.database) == (5432, "cookish_prod")


def test_a_secret_with_missing_fields_names_them_but_not_its_contents():
    with pytest.raises(RuntimeError) as caught:
        session.url_from_secret({"username": "u", "password": "super-secret-value"})
    assert "host" in str(caught.value)
    assert "super-secret-value" not in str(caught.value)


def test_the_secret_is_read_from_secrets_manager_by_its_name(monkeypatch):
    asked = []

    class FakeClient:
        def get_secret_value(self, SecretId):  # noqa: N803 - boto3's own name
            asked.append(SecretId)
            return {"SecretString": '{"username": "u", "password": "p", "host": "h"}'}

    fake = types.SimpleNamespace(client=lambda service: FakeClient() if service else None)
    monkeypatch.setitem(sys.modules, "boto3", fake)
    assert session._read_secret("arn:the-secret")["host"] == "h"
    assert asked == ["arn:the-secret"]
