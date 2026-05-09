"""Jinja filter tests — render templates through the Flask app."""

from __future__ import annotations

import pytest
import responses
from flask import Flask, render_template_string

from flask_unirate import UniRate

BASE = "https://api.unirateapi.com"


def _app(**extra: object) -> tuple[Flask, UniRate]:
    app = Flask(__name__)
    app.config["UNIRATE_API_KEY"] = "k"
    for k, v in extra.items():
        app.config[k] = v
    return app, UniRate(app)


def test_to_currency_uses_default_base(
    mocked_responses: responses.RequestsMock,
) -> None:
    mocked_responses.get(f"{BASE}/api/rates", json={"rate": "0.92"})
    app, _ext = _app()
    with app.app_context():
        rendered = render_template_string("{{ 100|to_currency('EUR') }}")
    assert float(rendered) == pytest.approx(92.0)


def test_to_currency_explicit_base_overrides_default(
    mocked_responses: responses.RequestsMock,
) -> None:
    mocked_responses.get(f"{BASE}/api/rates", json={"rate": "1.30"})
    app, _ext = _app()
    with app.app_context():
        rendered = render_template_string("{{ 50|to_currency('USD', 'GBP') }}")
    assert float(rendered) == pytest.approx(65.0)


def test_default_base_currency_config_respected(
    mocked_responses: responses.RequestsMock,
) -> None:
    mocked_responses.get(f"{BASE}/api/rates", json={"rate": "1.30"})
    app, _ext = _app(UNIRATE_DEFAULT_BASE_CURRENCY="GBP")
    with app.app_context():
        rendered = render_template_string("{{ 50|to_currency('USD') }}")
    assert float(rendered) == pytest.approx(65.0)
    sent_url = mocked_responses.calls[0].request.url or ""
    assert "from=GBP" in sent_url


def test_convert_currency_filter(
    mocked_responses: responses.RequestsMock,
) -> None:
    mocked_responses.get(f"{BASE}/api/rates", json={"rate": "0.78"})
    app, _ext = _app()
    with app.app_context():
        rendered = render_template_string("{{ 100|convert_currency('USD', 'GBP') }}")
    assert float(rendered) == pytest.approx(78.0)


def test_format_money_default_two_decimals() -> None:
    app, _ext = _app()
    with app.app_context():
        rendered = render_template_string("{{ 1234.567|format_money('USD') }}")
    assert rendered == "1,234.57 USD"


def test_format_money_btc_default_eight_decimals() -> None:
    app, _ext = _app()
    with app.app_context():
        rendered = render_template_string("{{ 0.123456789|format_money('btc') }}")
    assert rendered == "0.12345679 BTC"


def test_to_usd_alias(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f"{BASE}/api/rates", json={"rate": "1.10"})
    app, _ext = _app(UNIRATE_DEFAULT_BASE_CURRENCY="EUR")
    with app.app_context():
        rendered = render_template_string("{{ 100|to_usd }}")
    assert float(rendered) == pytest.approx(110.0)
    sent_url = mocked_responses.calls[0].request.url or ""
    assert "from=EUR" in sent_url and "to=USD" in sent_url


def test_to_eur_alias_with_explicit_base(
    mocked_responses: responses.RequestsMock,
) -> None:
    mocked_responses.get(f"{BASE}/api/rates", json={"rate": "0.92"})
    app, _ext = _app()
    with app.app_context():
        rendered = render_template_string("{{ 100|to_eur('USD') }}")
    assert float(rendered) == pytest.approx(92.0)
