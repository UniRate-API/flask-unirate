# flask-unirate

[![PyPI](https://img.shields.io/pypi/v/flask-unirate.svg)](https://pypi.org/project/flask-unirate/)
[![Python](https://img.shields.io/pypi/pyversions/flask-unirate.svg)](https://pypi.org/project/flask-unirate/)
[![License](https://img.shields.io/pypi/l/flask-unirate.svg)](https://github.com/UniRate-API/flask-unirate/blob/main/LICENSE)

Flask extension for the [UniRate](https://unirateapi.com) currency-exchange API:

- **Drop-in `UniRate(app)` extension** — follows the standard
  `init_app` factory pattern, registers itself on
  `app.extensions["unirate"]`.
- **Jinja filters** — `{{ amount|to_currency('EUR') }}`,
  `{{ amount|convert_currency('USD', 'JPY') }}`,
  `{{ price|format_money('USD') }}`, plus `to_usd` / `to_eur` / `to_gbp`
  shortcuts.
- **Optional Flask-Caching integration** — set
  `UNIRATE_CACHE_TIMEOUT` and the extension caches latest-rate /
  supported-currency lookups through whatever Flask-Caching backend you
  already have.
- Wraps the official [`unirate-api`](https://pypi.org/project/unirate-api/)
  Python client; full method surface is reachable through
  `unirate.client` if you need historical rates / VAT / time series.

UniRate covers 593+ fiat, crypto, and commodity codes. Latest rates and
conversion are on the free tier; historical endpoints
(`get_historical_rate`, `convert_historical`) require Pro.

## Install

```bash
pip install flask-unirate
```

With Flask-Caching support:

```bash
pip install "flask-unirate[caching]"
```

## Quick start

```python
import os

from flask import Flask, render_template_string

from flask_unirate import UniRate

app = Flask(__name__)
app.config["UNIRATE_API_KEY"] = os.environ["UNIRATE_API_KEY"]
unirate = UniRate(app)


@app.route("/rate/<base>/<quote>")
def rate(base: str, quote: str):
    return {"rate": unirate.get_rate(base, quote)}


@app.route("/checkout/<int:amount_usd>")
def checkout(amount_usd: int):
    return render_template_string(
        """
        <p>USD: {{ amount|format_money('USD') }}</p>
        <p>EUR: {{ amount|to_eur|format_money('EUR') }}</p>
        <p>JPY: {{ amount|to_currency('JPY')|format_money('JPY', decimals=0) }}</p>
        """,
        amount=amount_usd,
    )
```

## Configuration

| Key | Default | Notes |
|---|---|---|
| `UNIRATE_API_KEY` | — | Required. Falls back to the `UNIRATE_API_KEY` env var. |
| `UNIRATE_TIMEOUT` | 30 (s) | HTTP timeout passed to `UnirateClient`. |
| `UNIRATE_BASE_URL` | `https://api.unirateapi.com` | Override only if you proxy the API. |
| `UNIRATE_DEFAULT_BASE_CURRENCY` | `USD` | Default base for the `to_currency` Jinja filter. |
| `UNIRATE_CACHE_TIMEOUT` | unset | If set *and* Flask-Caching is initialised on the app, latest-rate / supported-currency lookups are cached for this many seconds. |

## Factory pattern

```python
from flask import Flask
from flask_unirate import UniRate

unirate = UniRate()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_pyfile("config.py")
    unirate.init_app(app)
    return app
```

Inside any view (or template) you can also reach the extension through
`current_app`:

```python
from flask import current_app

current_app.extensions["unirate"].get_rate("USD", "EUR")
```

…or through the convenience helper:

```python
from flask_unirate import get_unirate

get_unirate().get_rate("USD", "EUR")
```

## Jinja filters

Every filter is registered automatically when you call `UniRate(app)` /
`init_app(app)`:

| Filter | Example | Result |
|---|---|---|
| `to_currency(target, base=None)` | `{{ 100|to_currency('EUR') }}` | converts from the configured default base (USD) to EUR |
| `convert_currency(base, target)` | `{{ 100|convert_currency('USD', 'JPY') }}` | explicit base + target |
| `format_money(currency, decimals=2)` | `{{ 1234.5|format_money('USD') }}` | `1,234.50 USD` (BTC/ETH default to higher precision) |
| `to_usd` / `to_eur` / `to_gbp` | `{{ 100|to_eur }}` | shortcut filters bound to specific targets |

Chain them: `{{ amount|to_eur|format_money('EUR') }}`.

## Flask-Caching integration

```python
from flask import Flask
from flask_caching import Cache

from flask_unirate import UniRate

app = Flask(__name__)
app.config.update(
    UNIRATE_API_KEY="...",
    UNIRATE_CACHE_TIMEOUT=300,         # 5 minutes
    CACHE_TYPE="RedisCache",
    CACHE_REDIS_URL="redis://localhost",
)
Cache(app)
UniRate(app)
```

The extension auto-discovers the Cache instance off `app.extensions['cache']`
— so all of Flask-Caching's backends (SimpleCache, RedisCache, MemcachedCache,
FileSystemCache, …) work with no extra wiring. Failures fall through to a
fresh API call rather than raising.

## Errors

Errors come from the underlying `unirate-api` client and propagate
unchanged:

| HTTP | Exception class | Meaning |
|------|------------------|---------|
| 401 | `unirate.exceptions.AuthenticationError` | Missing or invalid API key |
| 404 | `unirate.exceptions.InvalidCurrencyError` | Currency not found |
| 429 | `unirate.exceptions.RateLimitError` | Rate limit exceeded |
| 503 | `unirate.exceptions.APIError` | Service unavailable |
| 403 | (raised as `requests.HTTPError` by `raise_for_status`) | Pro plan required (historical, commodities) |

Wrap the call site in `try / except UnirateError` to catch the whole
family.

## Compatibility

- Python 3.9 – 3.13
- Flask ≥ 2.0
- `unirate-api` ≥ 1.0
- (Optional) `flask-caching` ≥ 2.0

## Related

- [`unirate-api`](https://pypi.org/project/unirate-api/) — base sync
  Python client (this package wraps it).
- [`fastapi-unirate`](https://pypi.org/project/fastapi-unirate/) — async
  sibling for FastAPI.
- [`langchain-unirate`](https://pypi.org/project/langchain-unirate/) —
  LangChain partner package.
- Other UniRate integrations: dbt, Airflow, n8n, Raycast, MCP server.
  Full list at <https://unirateapi.com>.

<!-- unirate-ecosystem-footer:start -->
## UniRate ecosystem

UniRate ships official integrations for 40+ ecosystems, all maintained under the
[UniRate-API](https://github.com/UniRate-API) org.

**Core clients (9 languages)**
[Python](https://github.com/UniRate-API/unirate-api-python) ·
[Node.js / TypeScript](https://github.com/UniRate-API/unirate-api-nodejs) ·
[Go](https://github.com/UniRate-API/unirate-api-go) ·
[Rust](https://github.com/UniRate-API/unirate-api-rust) ·
[Java](https://github.com/UniRate-API/unirate-api-java) ·
[Ruby](https://github.com/UniRate-API/unirate-api-ruby) ·
[PHP](https://github.com/UniRate-API/unirate-api-php) ·
[.NET](https://github.com/UniRate-API/unirate-api-dotnet) ·
[Swift](https://github.com/UniRate-API/unirate-api-swift)

**JavaScript / TypeScript**
[React](https://github.com/UniRate-API/react-unirate) ·
[Next.js](https://github.com/UniRate-API/next-unirate) ·
[Remix](https://github.com/UniRate-API/remix-unirate) ·
[SvelteKit](https://github.com/UniRate-API/sveltekit-unirate) ·
[Vue](https://github.com/UniRate-API/vue-unirate) ·
[Angular](https://github.com/UniRate-API/angular-unirate) ·
[Nuxt](https://github.com/UniRate-API/nuxt-unirate) ·
[NestJS](https://github.com/UniRate-API/nestjs-unirate) ·
[tRPC](https://github.com/UniRate-API/trpc-unirate)

**Static-site generators**
[Astro](https://github.com/UniRate-API/astro-unirate) ·
[Eleventy](https://github.com/UniRate-API/eleventy-unirate) ·
[Hugo](https://github.com/UniRate-API/hugo-unirate) ·
[Jekyll](https://github.com/UniRate-API/jekyll-unirate)

**CMS & e-commerce**
[Wagtail](https://github.com/UniRate-API/wagtail-unirate) ·
[WordPress](https://github.com/UniRate-API/unirate-currency-converter) ·
[WooCommerce](https://github.com/UniRate-API/unirate-woocs) ·
[Drupal](https://github.com/UniRate-API/drupal-unirate) ·
[Strapi](https://github.com/UniRate-API/strapi-plugin-unirate) ·
[Medusa](https://github.com/UniRate-API/medusa-plugin-unirate) ·
[Symfony](https://github.com/UniRate-API/unirate-bundle) ·
[Laravel](https://github.com/UniRate-API/laravel-money-unirate) ·
[Directus](https://github.com/UniRate-API/directus-extension-unirate)

**Data, AI & backend**
[LangChain (Python)](https://github.com/UniRate-API/langchain-unirate) ·
[LangChain.js](https://github.com/UniRate-API/langchain-js-unirate) ·
[FastAPI](https://github.com/UniRate-API/fastapi-unirate) ·
[Flask](https://github.com/UniRate-API/flask-unirate) ·
[Django REST Framework](https://github.com/UniRate-API/djangorestframework-unirate) ·
[Apache Airflow](https://github.com/UniRate-API/airflow-provider-unirate) ·
[dbt](https://github.com/UniRate-API/dbt-unirate)

**Platform & tools**
[MCP server](https://github.com/UniRate-API/unirate-mcp) ·
[CLI](https://github.com/UniRate-API/unirate-cli) ·
[Cloudflare Workers](https://github.com/UniRate-API/cloudflare-workers-unirate) ·
[Home Assistant](https://github.com/UniRate-API/unirate-home-assistant) ·
[n8n](https://github.com/UniRate-API/n8n-nodes-unirate) ·
[Google Sheets](https://github.com/UniRate-API/unirate-sheets) ·
[VS Code](https://github.com/UniRate-API/vscode-unirate) ·
[Obsidian](https://github.com/UniRate-API/obsidian-currency)

**Money library bridges**
[money gem (Ruby)](https://github.com/UniRate-API/money-unirate-api) ·
[NodaMoney (.NET)](https://github.com/UniRate-API/UniRateApi.NodaMoney)

Get a free API key at [unirateapi.com](https://unirateapi.com).
<!-- unirate-ecosystem-footer:end -->

## License

MIT