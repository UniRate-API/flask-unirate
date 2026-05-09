"""Extension wiring + client lifecycle tests."""

from __future__ import annotations

import pytest
from flask import Flask
from unirate import UnirateClient

from flask_unirate import UniRate, get_unirate
from flask_unirate.extension import CLIENT_KEY, EXTENSION_KEY


def test_init_constructor_binds_immediately() -> None:
    app = Flask(__name__)
    app.config["UNIRATE_API_KEY"] = "k"
    ext = UniRate(app)
    assert app.extensions[EXTENSION_KEY] is ext


def test_init_app_factory_pattern() -> None:
    ext = UniRate()
    app = Flask(__name__)
    app.config["UNIRATE_API_KEY"] = "k"
    ext.init_app(app)
    assert app.extensions[EXTENSION_KEY] is ext


def test_init_app_double_registration_raises() -> None:
    app = Flask(__name__)
    app.config["UNIRATE_API_KEY"] = "k"
    UniRate(app)
    with pytest.raises(RuntimeError, match="already registered"):
        UniRate(app)


def test_get_unirate_helper_returns_extension() -> None:
    app = Flask(__name__)
    app.config["UNIRATE_API_KEY"] = "k"
    ext = UniRate(app)
    with app.app_context():
        assert get_unirate() is ext


def test_get_unirate_raises_when_not_initialised() -> None:
    app = Flask(__name__)
    with app.app_context():
        with pytest.raises(RuntimeError, match="not initialised"):
            get_unirate()


def test_client_lazily_built_from_config() -> None:
    app = Flask(__name__)
    app.config["UNIRATE_API_KEY"] = "config-key"
    ext = UniRate(app)
    assert CLIENT_KEY not in app.extensions
    with app.app_context():
        client = ext.client
    assert isinstance(client, UnirateClient)
    assert client.api_key == "config-key"
    # Cached for subsequent access.
    with app.app_context():
        assert ext.client is client


def test_client_falls_back_to_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UNIRATE_API_KEY", "env-key")
    app = Flask(__name__)  # no UNIRATE_API_KEY in app.config
    ext = UniRate(app)
    with app.app_context():
        assert ext.client.api_key == "env-key"


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UNIRATE_API_KEY", raising=False)
    app = Flask(__name__)
    ext = UniRate(app)
    with app.app_context():
        with pytest.raises(RuntimeError, match="API key not configured"):
            _ = ext.client


def test_explicit_client_passed_in() -> None:
    fake = UnirateClient(api_key="forced")
    app = Flask(__name__)
    UniRate(app, client=fake)
    with app.app_context():
        assert get_unirate().client is fake


def test_base_url_override_applies_to_client() -> None:
    app = Flask(__name__)
    app.config["UNIRATE_API_KEY"] = "k"
    app.config["UNIRATE_BASE_URL"] = "https://staging.example.com/"
    ext = UniRate(app)
    with app.app_context():
        assert ext.client.BASE_URL == "https://staging.example.com"


def test_timeout_override_applies_to_client() -> None:
    app = Flask(__name__)
    app.config["UNIRATE_API_KEY"] = "k"
    app.config["UNIRATE_TIMEOUT"] = 5
    ext = UniRate(app)
    with app.app_context():
        assert ext.client.timeout == 5
