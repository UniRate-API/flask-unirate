"""End-to-end tests of the extension's pass-through methods.

Mocks the upstream UniRate API at the HTTP layer with ``responses`` so the
real ``unirate.UnirateClient`` plumbing is exercised.
"""

from __future__ import annotations

import pytest
import responses
from flask import Flask
from responses import matchers

from flask_unirate import UniRate

BASE = "https://api.unirateapi.com"


def _app(api_key: str = "test-key", **extra: object) -> tuple[Flask, UniRate]:
    app = Flask(__name__)
    app.config["UNIRATE_API_KEY"] = api_key
    for k, v in extra.items():
        app.config[k] = v
    return app, UniRate(app)


def test_get_rate_returns_float(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(
        f"{BASE}/api/rates",
        json={"rate": "0.92"},
        match=[
            matchers.query_param_matcher(
                {"from": "USD", "to": "EUR", "api_key": "test-key"}
            )
        ],
    )
    app, ext = _app()
    with app.app_context():
        assert ext.get_rate("usd", "eur") == pytest.approx(0.92)


def test_convert_multiplies_rate(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f"{BASE}/api/rates", json={"rate": "1.10"})
    app, ext = _app()
    with app.app_context():
        out = ext.convert("EUR", "USD", 50)
    assert out == pytest.approx(55.0)


def test_convert_same_currency_skips_request(
    mocked_responses: responses.RequestsMock,
) -> None:
    # No mock registered: any HTTP call would error out.
    app, ext = _app()
    with app.app_context():
        assert ext.convert("USD", "USD", 100) == pytest.approx(100.0)
    assert len(mocked_responses.calls) == 0


def test_get_supported_currencies(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(
        f"{BASE}/api/currencies", json={"currencies": ["USD", "EUR", "BTC"]}
    )
    app, ext = _app()
    with app.app_context():
        assert ext.get_supported_currencies() == ["USD", "EUR", "BTC"]


def test_get_historical_rate(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(
        f"{BASE}/api/historical/rates",
        json={"rate": "0.91"},
        match=[
            matchers.query_param_matcher(
                {
                    "from": "USD",
                    "to": "EUR",
                    "amount": "1",
                    "date": "2024-01-15",
                    "api_key": "test-key",
                }
            )
        ],
    )
    app, ext = _app()
    with app.app_context():
        out = ext.get_historical_rate("usd", "eur", "2024-01-15")
    assert out == pytest.approx(0.91)


def test_convert_historical(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(
        f"{BASE}/api/historical/rates",
        json={"result": "91.0"},
        match=[
            matchers.query_param_matcher(
                {
                    "from": "USD",
                    "to": "EUR",
                    "amount": "100",
                    "date": "2024-01-15",
                    "api_key": "test-key",
                }
            )
        ],
    )
    app, ext = _app()
    with app.app_context():
        out = ext.convert_historical("usd", "eur", 100, "2024-01-15")
    assert out == pytest.approx(91.0)


def test_view_uses_extension_via_current_app(
    mocked_responses: responses.RequestsMock,
) -> None:
    mocked_responses.get(f"{BASE}/api/rates", json={"rate": "150.5"})

    app, _ext = _app()

    @app.get("/rate/<base>/<quote>")
    def rate(base: str, quote: str) -> dict[str, float]:
        from flask_unirate import get_unirate

        return {"rate": get_unirate().get_rate(base, quote)}

    client = app.test_client()
    response = client.get("/rate/usd/jpy")
    assert response.status_code == 200
    assert response.json == {"rate": 150.5}


def test_query_string_includes_api_key(
    mocked_responses: responses.RequestsMock,
) -> None:
    mocked_responses.get(f"{BASE}/api/rates", json={"rate": "1.0"})
    app, ext = _app(api_key="secret-key")
    with app.app_context():
        ext.get_rate("USD", "EUR")
    sent_url = mocked_responses.calls[0].request.url or ""
    assert "api_key=secret-key" in sent_url


# ------------------------------------------------------------------
# Error mapping — surfaces the underlying ``unirate`` exception types,
# unchanged. We just verify they propagate.
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "exc_substr"),
    [
        (401, "AuthenticationError"),
        (404, "InvalidCurrencyError"),
        (429, "RateLimitError"),
    ],
)
def test_error_propagation(
    mocked_responses: responses.RequestsMock,
    status: int,
    exc_substr: str,
) -> None:
    mocked_responses.get(f"{BASE}/api/rates", status=status, json={"error": "x"})
    app, ext = _app()
    with app.app_context():
        with pytest.raises(Exception) as excinfo:
            ext.get_rate("USD", "EUR")
    assert exc_substr in type(excinfo.value).__name__


# ------------------------------------------------------------------
# Caching integration
# ------------------------------------------------------------------


def test_caching_short_circuits_second_call(
    mocked_responses: responses.RequestsMock,
) -> None:
    pytest.importorskip("flask_caching")
    from flask_caching import Cache

    mocked_responses.get(f"{BASE}/api/rates", json={"rate": "1.10"})

    app = Flask(__name__)
    app.config.update(
        UNIRATE_API_KEY="k",
        UNIRATE_CACHE_TIMEOUT=60,
        CACHE_TYPE="SimpleCache",
    )
    Cache(app)
    ext = UniRate(app)

    with app.app_context():
        first = ext.get_rate("USD", "EUR")
        second = ext.get_rate("USD", "EUR")

    assert first == pytest.approx(1.10)
    assert second == pytest.approx(1.10)
    assert len(mocked_responses.calls) == 1, (
        "Second call should be served from Flask-Caching"
    )


def test_caching_disabled_when_timeout_unset(
    mocked_responses: responses.RequestsMock,
) -> None:
    pytest.importorskip("flask_caching")
    from flask_caching import Cache

    mocked_responses.get(f"{BASE}/api/rates", json={"rate": "1.10"})
    mocked_responses.get(f"{BASE}/api/rates", json={"rate": "1.10"})

    app = Flask(__name__)
    app.config.update(UNIRATE_API_KEY="k", CACHE_TYPE="SimpleCache")
    Cache(app)
    ext = UniRate(app)

    with app.app_context():
        ext.get_rate("USD", "EUR")
        ext.get_rate("USD", "EUR")

    assert len(mocked_responses.calls) == 2
