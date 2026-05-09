"""``UniRate`` Flask extension.

Wires a single :class:`unirate.UnirateClient` per Flask app, registers a set
of Jinja filters, and optionally caches latest-rate / convert lookups
through ``Flask-Caching`` if it is configured.

Usage:

.. code-block:: python

    from flask import Flask
    from flask_unirate import UniRate

    app = Flask(__name__)
    app.config["UNIRATE_API_KEY"] = "..."
    unirate = UniRate(app)

    @app.route("/rate/<base>/<quote>")
    def rate(base, quote):
        return {"rate": unirate.get_rate(base, quote)}
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast

from flask import Flask, current_app

if TYPE_CHECKING:
    from unirate import UnirateClient

EXTENSION_KEY = "unirate"
CLIENT_KEY = "unirate_client"

CONFIG_API_KEY = "UNIRATE_API_KEY"
CONFIG_TIMEOUT = "UNIRATE_TIMEOUT"
CONFIG_BASE_URL = "UNIRATE_BASE_URL"
CONFIG_CACHE_TIMEOUT = "UNIRATE_CACHE_TIMEOUT"
CONFIG_DEFAULT_BASE = "UNIRATE_DEFAULT_BASE_CURRENCY"

T = TypeVar("T")


class UniRate:
    """Flask extension exposing a UniRate client + Jinja filters.

    Args:
        app: Optional Flask app to bind on construction. If omitted, call
            :meth:`init_app` later (the standard factory pattern).
        client: Pre-built :class:`unirate.UnirateClient`. Mostly useful in
            tests where the client is mocked.

    Configuration keys read from ``app.config``:
        - ``UNIRATE_API_KEY`` — required (or falls back to the
            ``UNIRATE_API_KEY`` environment variable).
        - ``UNIRATE_BASE_URL`` — override the API base URL (rare).
        - ``UNIRATE_TIMEOUT`` — request timeout in seconds (default 30).
        - ``UNIRATE_CACHE_TIMEOUT`` — if set and ``Flask-Caching`` is
            initialised on the app, latest-rate / convert / supported-
            currencies lookups are cached for that many seconds.
        - ``UNIRATE_DEFAULT_BASE_CURRENCY`` — default base for the
            ``to_currency`` Jinja filter (default ``"USD"``).
    """

    def __init__(
        self,
        app: Flask | None = None,
        *,
        client: UnirateClient | None = None,
    ) -> None:
        self._explicit_client = client
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Bind the extension to ``app`` and register Jinja filters."""
        app.extensions = getattr(app, "extensions", {})
        if EXTENSION_KEY in app.extensions:
            msg = (
                "A UniRate extension is already registered on this Flask app. "
                "Call init_app at most once per app."
            )
            raise RuntimeError(msg)
        app.extensions[EXTENSION_KEY] = self
        if self._explicit_client is not None:
            app.extensions[CLIENT_KEY] = self._explicit_client

        app.config.setdefault(CONFIG_DEFAULT_BASE, "USD")

        from flask_unirate.filters import register_filters

        register_filters(app)

    # ------------------------------------------------------------------
    # Client access
    # ------------------------------------------------------------------

    @property
    def client(self) -> UnirateClient:
        """Return the underlying :class:`unirate.UnirateClient`.

        Lazily instantiated on first access so apps that read the API key
        from env / vault at request time still work.
        """
        app = current_app._get_current_object()  # type: ignore[attr-defined]
        cached = app.extensions.get(CLIENT_KEY)
        if cached is not None:
            return cast("UnirateClient", cached)
        client = self._build_client(app)
        app.extensions[CLIENT_KEY] = client
        return client

    @staticmethod
    def _build_client(app: Flask) -> UnirateClient:
        from unirate import UnirateClient

        api_key = app.config.get(CONFIG_API_KEY) or os.environ.get(CONFIG_API_KEY)
        if not api_key:
            msg = (
                "UniRate API key not configured. Set app.config['UNIRATE_API_KEY'] "
                "or the UNIRATE_API_KEY environment variable."
            )
            raise RuntimeError(msg)

        kwargs: dict[str, Any] = {"api_key": api_key}
        timeout = app.config.get(CONFIG_TIMEOUT)
        if timeout is not None:
            kwargs["timeout"] = timeout
        client = UnirateClient(**kwargs)
        # ``UnirateClient`` exposes BASE_URL as a class attribute; override it
        # on the instance only if the app explicitly asked for a different
        # endpoint (rare — testing, self-hosted proxy).
        base_url = app.config.get(CONFIG_BASE_URL)
        if base_url is not None:
            client.BASE_URL = base_url.rstrip("/")
        return client

    # ------------------------------------------------------------------
    # Convenience pass-throughs (with optional Flask-Caching wrapping)
    # ------------------------------------------------------------------

    def get_rate(self, from_currency: str, to_currency: str) -> float:
        """Latest exchange rate for the ``from -> to`` pair."""
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        cache_key = f"unirate:rate:{from_currency}:{to_currency}"

        def _fetch() -> float:
            return float(
                self.client.get_rate(
                    from_currency=from_currency, to_currency=to_currency
                )
            )

        return self._cached(cache_key, _fetch)

    def convert(self, from_currency: str, to_currency: str, amount: float) -> float:
        """Convert ``amount`` between two currencies at the latest rate."""
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        if from_currency == to_currency:
            return float(amount)
        rate = self.get_rate(from_currency, to_currency)
        return float(amount) * rate

    def get_supported_currencies(self) -> list[str]:
        """Return the list of every supported currency code."""
        cache_key = "unirate:currencies"

        def _fetch() -> list[str]:
            return list(self.client.get_supported_currencies())

        return self._cached(cache_key, _fetch)

    def get_historical_rate(
        self, from_currency: str, to_currency: str, date: str
    ) -> float:
        """Historical rate on ``date`` (YYYY-MM-DD). Pro-gated."""
        return float(
            self.client.get_historical_rate(
                from_currency=from_currency.upper(),
                to_currency=to_currency.upper(),
                date=date,
            )
        )

    def convert_historical(
        self,
        from_currency: str,
        to_currency: str,
        amount: float,
        date: str,
    ) -> float:
        """Convert ``amount`` at the rate observed on ``date``. Pro-gated."""
        return float(
            self.client.convert_historical(
                from_currency=from_currency.upper(),
                to_currency=to_currency.upper(),
                amount=amount,
                date=date,
            )
        )

    # ------------------------------------------------------------------
    # Caching helper
    # ------------------------------------------------------------------

    def _cached(self, key: str, fetch: Callable[[], T]) -> T:
        cache = self._resolve_cache()
        if cache is None:
            return fetch()
        try:
            cached_value = cache.get(key)
        except Exception:
            cached_value = None
        if cached_value is not None:
            return cast(T, cached_value)
        value = fetch()
        timeout = current_app.config.get(CONFIG_CACHE_TIMEOUT)
        try:
            if timeout is not None:
                cache.set(key, value, timeout=timeout)
            else:
                cache.set(key, value)
        except Exception:
            pass
        return value

    @staticmethod
    def _resolve_cache() -> Any | None:
        timeout = current_app.config.get(CONFIG_CACHE_TIMEOUT)
        if timeout is None:
            return None
        cache = current_app.extensions.get("cache")
        if cache is None:
            return None
        # Flask-Caching 2.x stores ``app.extensions['cache']`` as a dict
        # ``{Cache: app}`` while older releases stored the Cache instance
        # directly. Accept either shape.
        if isinstance(cache, dict):
            for instance in cache:
                return instance
            return None
        return cache


def get_unirate(app: Flask | None = None) -> UniRate:
    """Return the :class:`UniRate` extension registered on ``app``.

    If no app is passed, the current Flask app context is used.
    """
    target = app if app is not None else current_app._get_current_object()  # type: ignore[attr-defined]
    extensions = getattr(target, "extensions", {})
    ext: UniRate | None = extensions.get(EXTENSION_KEY)
    if ext is None:
        msg = (
            "UniRate extension is not initialised on this app — "
            "call UniRate(app) or UniRate().init_app(app) first."
        )
        raise RuntimeError(msg)
    return ext


__all__ = [
    "UniRate",
    "get_unirate",
]
