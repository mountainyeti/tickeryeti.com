import pytest
import requests

API_BASE = 'https://0mzipto7d3.execute-api.us-east-1.amazonaws.com'


# ── Happy path ─────────────────────────────────────────────────────────────────

def test_valid_ticker_returns_200():
    r = requests.get(f'{API_BASE}/?ticker=AAPL', timeout=20)
    assert r.status_code == 200

def test_response_is_json():
    r = requests.get(f'{API_BASE}/?ticker=AAPL', timeout=20)
    assert r.headers['Content-Type'] == 'application/json'
    r.json()  # raises if not valid JSON

def test_lowercase_ticker_accepted():
    r = requests.get(f'{API_BASE}/?ticker=aapl', timeout=20)
    assert r.status_code == 200
    assert r.json()['ticker'] == 'AAPL'

def test_required_top_level_fields():
    r = requests.get(f'{API_BASE}/?ticker=AAPL', timeout=20)
    data = r.json()
    for field in ['ticker', 'name', 'sector', 'industry', 'exchange', 'series', 'stats', 'fin', 'peers']:
        assert field in data, f'Missing field: {field}'

def test_stats_fields_present():
    r = requests.get(f'{API_BASE}/?ticker=MSFT', timeout=20)
    stats = r.json()['stats']
    for field in ['mcap', 'pe', 'pb', 'ps', 'shares', 'avg_vol', 'curr_ratio', 'de_ratio', 'int_cov']:
        assert field in stats, f'Missing stats field: {field}'

def test_price_series_has_data():
    r = requests.get(f'{API_BASE}/?ticker=AAPL', timeout=20)
    series = r.json()['series']
    assert len(series) > 100  # should have years of history
    point = series[0]
    assert 'd' in point and 'p' in point and 'v' in point

def test_financial_rows_present():
    r = requests.get(f'{API_BASE}/?ticker=AAPL', timeout=20)
    fin = r.json()['fin']
    assert len(fin) >= 1
    row = fin[0]
    for field in ['yr', 'rev', 'ni', 'eps', 'ebitda']:
        assert field in row, f'Missing fin field: {field}'

def test_peers_is_list():
    r = requests.get(f'{API_BASE}/?ticker=AAPL', timeout=20)
    assert isinstance(r.json()['peers'], list)


# ── Error cases ────────────────────────────────────────────────────────────────

def test_unknown_ticker_returns_404():
    # ZZZT is a valid-format but non-existent ticker
    r = requests.get(f'{API_BASE}/?ticker=ZZZT', timeout=20)
    assert r.status_code == 404
    assert 'error' in r.json()

def test_bad_symbol_characters_returns_400():
    r = requests.get(f'{API_BASE}/?ticker=<script>', timeout=20)
    assert r.status_code == 400

def test_empty_ticker_returns_400():
    r = requests.get(f'{API_BASE}/?ticker=', timeout=20)
    assert r.status_code == 400

def test_missing_ticker_param_returns_400():
    r = requests.get(f'{API_BASE}/', timeout=20)
    assert r.status_code == 400


# ── CORS ───────────────────────────────────────────────────────────────────────

def test_cors_header_on_get():
    # API Gateway only reflects CORS headers when Origin is present
    r = requests.get(f'{API_BASE}/?ticker=AAPL', timeout=20,
                     headers={'Origin': 'https://tickeryeti.com'})
    assert r.headers.get('Access-Control-Allow-Origin') == '*'

def test_options_preflight_returns_success():
    # API Gateway handles OPTIONS at the gateway level — returns 204, no Lambda invocation
    r = requests.options(f'{API_BASE}/', timeout=10,
                         headers={'Origin': 'https://tickeryeti.com'})
    assert r.status_code in (200, 204)
