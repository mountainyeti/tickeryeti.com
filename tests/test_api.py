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


# ── Data quality ───────────────────────────────────────────────────────────────

def test_ipo_year_accuracy():
    """FMP-sourced IPO years should match known values, not the 5-year series start.
    '—' is accepted when FMP's free-tier rate limit is exhausted (resets daily).
    """
    cases = [
        ('AAPL', '1980'),  # Apple IPO Dec 1980
        ('MSFT', '1986'),  # Microsoft IPO Mar 1986
    ]
    for ticker, expected_year in cases:
        r = requests.get(f'{API_BASE}/?ticker={ticker}', timeout=20)
        ipo = r.json().get('ipo_year', '')
        assert ipo in (expected_year, '—'), (
            f'{ticker}: expected IPO year {expected_year} (or "—" if FMP rate-limited), got {ipo!r}. '
            f'A non-blank wrong year means we are incorrectly deriving it from the price series.'
        )

def test_ipo_year_not_derived_from_series():
    """Old-company IPO years must not equal the 5-year series start (~2021)."""
    old_tickers = ['IBM', 'GE', 'KO']  # all listed decades before 2021
    for ticker in old_tickers:
        r = requests.get(f'{API_BASE}/?ticker={ticker}', timeout=20)
        ipo = r.json().get('ipo_year', '')
        assert ipo != '2021', (
            f'{ticker}: ipo_year is "2021" — this is the 5-year series start, not the real IPO year.'
        )
        assert ipo == '—' or int(ipo) < 2000, (
            f'{ticker}: ipo_year {ipo!r} looks wrong for a company listed well before 2000.'
        )

def test_financial_years_are_distinct():
    """Three years of financials must have three different year labels.

    A regression test for the df_val bug where all years returned identical
    data (the most-recent year repeated), making YoY deltas always 0%.
    """
    r = requests.get(f'{API_BASE}/?ticker=AAPL', timeout=20)
    fin = r.json()['fin']
    assert len(fin) == 3, f'Expected 3 fin rows, got {len(fin)}'
    years = [row['yr'] for row in fin]
    assert len(set(years)) == 3, (
        f'Financial year labels are not distinct: {years}. '
        f'Likely the same year\'s data repeated across all columns.'
    )

def test_financial_values_vary_across_years():
    """Revenue figures must differ between at least two years.

    Guards against the df_val bug where every year column returned
    the same value, producing 0% YoY change everywhere.
    """
    r = requests.get(f'{API_BASE}/?ticker=AAPL', timeout=20)
    fin = r.json()['fin']
    assert len(fin) >= 2
    revenues = [row.get('rev') for row in fin if row.get('rev') is not None]
    assert len(revenues) >= 2, 'Not enough non-null revenue values to compare'
    assert len(set(revenues)) > 1, (
        f'Revenue is identical across all years ({revenues[0]}). '
        f'Likely all rows contain the same year\'s data.'
    )

def test_company_name_matches_ticker():
    """Spot-check that company names correspond to their tickers."""
    cases = [
        ('AAPL', 'apple'),
        ('MSFT', 'microsoft'),
        ('AMZN', 'amazon'),
    ]
    for ticker, expected_fragment in cases:
        r = requests.get(f'{API_BASE}/?ticker={ticker}', timeout=20)
        name = r.json().get('name', '').lower()
        assert expected_fragment in name, (
            f'{ticker}: expected name to contain "{expected_fragment}", got {name!r}'
        )

def test_series_prices_are_positive():
    """Every price in the series must be a positive number."""
    r = requests.get(f'{API_BASE}/?ticker=AAPL', timeout=20)
    series = r.json()['series']
    bad = [p for p in series if not isinstance(p.get('p'), (int, float)) or p['p'] <= 0]
    assert not bad, f'Found {len(bad)} series points with non-positive prices: {bad[:3]}'

def test_stat_values_are_strings_or_dash():
    """Formatted stat values must be non-empty strings — never null or empty."""
    r = requests.get(f'{API_BASE}/?ticker=AAPL', timeout=20)
    stats = r.json()['stats']
    for key, val in stats.items():
        assert isinstance(val, str) and len(val) > 0, (
            f'stats.{key} is {val!r} — should be a formatted string or "—"'
        )


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
