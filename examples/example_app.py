"""End-to-end Flask demo for flask-unirate.

Run:

    UNIRATE_API_KEY=... flask --app examples.example_app run

Then:

    curl http://127.0.0.1:5000/rate/USD/EUR
    curl http://127.0.0.1:5000/convert/USD/JPY/100
    curl http://127.0.0.1:5000/checkout/49
"""

from __future__ import annotations

import os

from flask import Flask, render_template_string

from flask_unirate import UniRate

app = Flask(__name__)
app.config.update(
    UNIRATE_API_KEY=os.environ.get("UNIRATE_API_KEY", ""),
    UNIRATE_DEFAULT_BASE_CURRENCY="USD",
)
unirate = UniRate(app)


@app.route("/rate/<base>/<quote>")
def rate(base: str, quote: str) -> dict[str, float]:
    """Latest rate, untemplated."""
    return {"rate": unirate.get_rate(base, quote)}


@app.route("/convert/<base>/<quote>/<float:amount>")
def convert(base: str, quote: str, amount: float) -> dict[str, float]:
    """Convert ``amount`` from ``base`` to ``quote``."""
    return {"result": unirate.convert(base, quote, amount)}


CHECKOUT_TEMPLATE = """
<!doctype html>
<title>Pricing</title>
<h1>Widget</h1>
<dl>
  <dt>USD</dt><dd>{{ amount|format_money('USD') }}</dd>
  <dt>EUR</dt><dd>{{ amount|to_eur|format_money('EUR') }}</dd>
  <dt>GBP</dt><dd>{{ amount|to_gbp|format_money('GBP') }}</dd>
  <dt>JPY</dt><dd>{{ amount|to_currency('JPY')|format_money('JPY', decimals=0) }}</dd>
</dl>
"""


@app.route("/checkout/<int:amount>")
def checkout(amount: int) -> str:
    """Demonstrates the Jinja filter chain."""
    return render_template_string(CHECKOUT_TEMPLATE, amount=amount)


if __name__ == "__main__":
    app.run(debug=True)
