"""Shared pytest fixtures for the flask-unirate test suite.

We mock the UniRate API at the *HTTP* layer (via ``responses``) rather than
swapping the client out, so the tests exercise the real
``unirate.UnirateClient`` plumbing the extension wires up.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import responses
from flask import Flask

from flask_unirate import UniRate

UNIRATE_BASE = "https://api.unirateapi.com"


@pytest.fixture
def mocked_responses() -> Iterator[responses.RequestsMock]:
    """A fresh ``responses`` mock context per test."""
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        yield mock


@pytest.fixture
def make_app() -> Any:
    """Factory: build a fresh Flask app + UniRate extension with overrides."""

    def _make(
        *,
        api_key: str = "test-key",
        config: dict[str, Any] | None = None,
        init_extension: bool = True,
    ) -> tuple[Flask, UniRate | None]:
        app = Flask(__name__)
        app.config["TESTING"] = True
        if api_key is not None:
            app.config["UNIRATE_API_KEY"] = api_key
        if config:
            app.config.update(config)
        ext = UniRate(app) if init_extension else None
        return app, ext

    return _make
