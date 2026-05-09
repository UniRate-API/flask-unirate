"""Jinja filters registered on the Flask app by :class:`UniRate.init_app`.

Every filter is also exported as a top-level function so callers can apply
them outside of templates (e.g. inside a view that builds JSON).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Flask, current_app

if TYPE_CHECKING:
    pass


def register_filters(app: Flask) -> None:
    """Attach the UniRate Jinja filters to ``app``."""
    app.add_template_filter(to_currency_filter, name="to_currency")
    app.add_template_filter(convert_currency_filter, name="convert_currency")
    app.add_template_filter(format_money_filter, name="format_money")

    # Convenience aliases for the most common targets.
    app.add_template_filter(_make_target_filter("USD"), name="to_usd")
    app.add_template_filter(_make_target_filter("EUR"), name="to_eur")
    app.add_template_filter(_make_target_filter("GBP"), name="to_gbp")


def to_currency_filter(amount: float, target: str, base: str | None = None) -> float:
    """``{{ amount|to_currency('EUR') }}`` — convert from default base.

    The default base is ``app.config['UNIRATE_DEFAULT_BASE_CURRENCY']``
    (``"USD"`` if unset). Pass ``base`` to override per-call.
    """
    from flask_unirate.extension import CONFIG_DEFAULT_BASE, get_unirate

    base = base or current_app.config.get(CONFIG_DEFAULT_BASE, "USD")
    return get_unirate().convert(base, target, float(amount))


def convert_currency_filter(amount: float, base: str, target: str) -> float:
    """``{{ amount|convert_currency('USD', 'EUR') }}`` — explicit base + target."""
    from flask_unirate.extension import get_unirate

    return get_unirate().convert(base, target, float(amount))


def format_money_filter(amount: float, currency: str, *, decimals: int = 2) -> str:
    """``{{ price|format_money('USD') }}`` → ``"123.45 USD"``.

    Light-weight formatter that doesn't pull in Babel. Use ``decimals`` to
    override; common crypto codes default to 8.
    """
    code = currency.upper()
    if decimals == 2 and code in _CRYPTO_DEFAULT_DECIMALS:
        decimals = _CRYPTO_DEFAULT_DECIMALS[code]
    return f"{float(amount):,.{decimals}f} {code}"


_CRYPTO_DEFAULT_DECIMALS = {
    "BTC": 8,
    "ETH": 6,
    "XBT": 8,
}


def _make_target_filter(target_code: str):  # type: ignore[no-untyped-def]
    """Build a ``to_<currency>`` filter bound to a specific target code."""

    def _filter(amount: float, base: str | None = None) -> float:
        return to_currency_filter(amount, target_code, base=base)

    _filter.__name__ = f"to_{target_code.lower()}"
    _filter.__doc__ = (
        f"Convert ``amount`` (in the configured default base, USD by default) "
        f"into {target_code} at the latest rate."
    )
    return _filter


__all__ = [
    "convert_currency_filter",
    "format_money_filter",
    "register_filters",
    "to_currency_filter",
]
