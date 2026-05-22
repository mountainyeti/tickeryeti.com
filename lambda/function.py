import json
import os
import re
import time
import urllib.request
import urllib.error
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import yfinance as yf
import pandas as pd

# Lambda filesystem is read-only except /tmp — redirect yfinance caches there.
# Note: keep Lambda memory at 512MB — Lambda allocates CPU proportionally to memory,
# and yfinance/pandas are CPU-bound. At 256MB requests took 2x longer (2900ms vs 1400ms).
yf.set_tz_cache_location('/tmp')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# In-memory response cache — survives across warm Lambda invocations
_cache = {}
CACHE_TTL = 900  # 15 minutes

FMP_BASE = 'https://financialmodelingprep.com/stable'
FMP_KEY  = os.environ['FMP_KEY']

CORS = {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Content-Type': 'application/json',
}

# ── Entry ──────────────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    method = (event.get('requestContext') or {}).get('http', {}).get('method', 'GET')
    if method == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS, 'body': ''}
    if method == 'POST':
        return handle_feedback(event)
    params = event.get('queryStringParameters') or {}
    sym = (params.get('ticker') or '').upper().strip()
    if not sym or not re.match(r'^[A-Z0-9.\-]{1,10}$', sym):
        return err(400, 'Invalid ticker symbol')
    period = params.get('period') or '5y'
    if period not in ('5y', '10y'):
        period = '5y'
    cache_key = sym if period == '5y' else f'{sym}:10y'
    try:
        # Serve from cache if fresh
        cached = _cache.get(cache_key)
        if cached and time.time() - cached[0] < CACHE_TTL:
            logger.info(f'Cache hit: {cache_key}')
            return {'statusCode': 200, 'headers': CORS, 'body': cached[1]}

        data = build_response(sym, period)
        body = json.dumps(data)
        _cache[cache_key] = (time.time(), body)
        return {'statusCode': 200, 'headers': CORS, 'body': body}
    except NotFound:
        return err(404, f'No data found for {sym}')
    except Exception as e:
        logger.exception('Unhandled error')
        return err(500, str(e))

def err(code, msg):
    return {'statusCode': code, 'headers': CORS, 'body': json.dumps({'error': msg})}

def handle_feedback(event):
    import base64
    raw = event.get('body') or ''
    if event.get('isBase64Encoded'):
        raw = base64.b64decode(raw).decode('utf-8')
    try:
        data = json.loads(raw)
    except Exception:
        return err(400, 'Invalid JSON')

    # Honeypot — bots fill the hidden website field, humans don't
    if data.get('website'):
        return {'statusCode': 200, 'headers': CORS, 'body': json.dumps({'ok': True})}

    message = (data.get('message') or '').strip()
    if not message or len(message) < 5:
        return err(400, 'Message too short')
    if len(message) > 2000:
        return err(400, 'Message too long')

    ftype   = (data.get('type') or 'Feedback').strip()[:50]
    name    = (data.get('name') or '').strip()[:100]
    email   = (data.get('email') or '').strip()[:200]

    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        return err(500, 'Feedback not configured')

    title = f'[{ftype}] {message[:60]}{"..." if len(message) > 60 else ""}'
    lines = [f'**Type:** {ftype}', '', '**Message:**', message, '']
    if name:
        lines.append(f'**Name:** {name}')
    if email:
        lines.append(f'**Email:** {email}')
    lines += ['', '*Submitted via tickeryeti.com feedback form*']

    payload = json.dumps({'title': title, 'body': '\n'.join(lines)}).encode()
    req = urllib.request.Request(
        'https://api.github.com/repos/mountainyeti/tickeryeti.com/issues',
        data=payload,
        headers={
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
            'User-Agent': 'TickerYeti-Lambda',
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            issue = json.loads(resp.read())
            return {'statusCode': 200, 'headers': CORS, 'body': json.dumps({'ok': True, 'issue': issue['number']})}
    except urllib.error.HTTPError as e:
        logger.error(f'GitHub API error: {e.code} {e.read()}')
        return err(502, 'Could not submit feedback')

class NotFound(Exception):
    pass

# ── Helpers ────────────────────────────────────────────────────────────────────

def safe_float(v, default=None):
    try:
        f = float(v)
        return f if f == f else default  # filter NaN
    except (TypeError, ValueError):
        return default

def bn(v):
    """Convert raw dollar value to $B, return None if missing/zero."""
    f = safe_float(v)
    if f is None or f == 0:
        return None
    return round(f / 1e9, 2)

def fmt_cap(v):
    f = safe_float(v)
    if f is None or f == 0: return '—'
    if abs(f) >= 1e12: return f'${f/1e12:.2f}T'
    if abs(f) >= 1e9:  return f'${f/1e9:.2f}B'
    if abs(f) >= 1e6:  return f'${f/1e6:.2f}M'
    return f'${f:,.0f}'

def fmt_count(v):
    f = safe_float(v)
    if f is None or f == 0: return '—'
    if abs(f) >= 1e9: return f'{f/1e9:.2f}B'
    if abs(f) >= 1e6: return f'{f/1e6:.2f}M'
    return f'{f:,.0f}'

def fmt_num(v, dp=2):
    f = safe_float(v)
    return str(round(f, dp)) if f is not None else '—'

def df_val(df, *row_names):
    """Get the first non-null value from a DataFrame row, searching by name."""
    if df is None or df.empty:
        return None
    for name in row_names:
        if name in df.index:
            row = df.loc[name]
            for val in row:
                f = safe_float(val)
                if f is not None:
                    return f
    return None

STATE_MAP = {
    'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California',
    'CO':'Colorado','CT':'Connecticut','DE':'Delaware','FL':'Florida','GA':'Georgia',
    'HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa',
    'KS':'Kansas','KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland',
    'MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi','MO':'Missouri',
    'MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey',
    'NM':'New Mexico','NY':'New York','NC':'North Carolina','ND':'North Dakota','OH':'Ohio',
    'OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina',
    'SD':'South Dakota','TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont',
    'VA':'Virginia','WA':'Washington','WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming'
}

# ── IPO date from FMP profile ─────────────────────────────────────────────────

def _fmp_ipo_year(sym):
    """Return 4-digit IPO year string from FMP profile, or None if unavailable."""
    try:
        url = f'{FMP_BASE}/profile?symbol={sym}&apikey={FMP_KEY}'
        req = urllib.request.Request(url, headers={'User-Agent': 'tickeryeti/1.0'})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read())
        profile = data[0] if isinstance(data, list) and data else data
        ipo_date = profile.get('ipoDate') if isinstance(profile, dict) else None
        if ipo_date and len(ipo_date) >= 4:
            return ipo_date[:4]
    except Exception:
        pass
    return None

# ── Peers: FMP primary, Yahoo Finance fallback ────────────────────────────────

def fetch_peers(sym):
    """Try FMP first (curated industry peers), fall back to Yahoo similar stocks."""
    peers = _fmp_peers(sym)
    if not peers:
        peers = _yf_peers(sym)
    return peers

def _fmp_peers(sym):
    try:
        url = f'{FMP_BASE}/stock-peers?symbol={sym}&apikey={FMP_KEY}'
        req = urllib.request.Request(url, headers={'User-Agent': 'tickeryeti/1.0'})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict) and 'symbol' in first:
                return [p['symbol'] for p in data if p.get('symbol') != sym][:8]
    except Exception as e:
        logger.info(f'FMP peers unavailable ({e}), trying Yahoo Finance')
    return []

def _yf_peers(sym):
    """Yahoo Finance recommended symbols — similar companies by Yahoo's model."""
    try:
        url = f'https://query1.finance.yahoo.com/v6/finance/recommendationsbysymbol/{sym}'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        result = data.get('finance', {}).get('result', [])
        if result:
            return [s['symbol'] for s in result[0].get('recommendedSymbols', [])
                    if s.get('symbol') != sym][:8]
    except Exception as e:
        logger.warning(f'YF peers failed: {e}')
    return []

# ── Main ───────────────────────────────────────────────────────────────────────

def build_response(sym, period='5y'):
    ticker = yf.Ticker(sym)

    # Fetch all data in parallel — info is now included in the pool
    with ThreadPoolExecutor(max_workers=5) as ex:
        hist_fut  = ex.submit(lambda: ticker.history(period=period))
        fin_fut   = ex.submit(fetch_financials, ticker)
        peers_fut = ex.submit(fetch_peers, sym)
        info_fut  = ex.submit(lambda: ticker.info or {})
        ipo_fut   = ex.submit(_fmp_ipo_year, sym)

    info  = info_fut.result()
    name  = info.get('longName') or info.get('shortName') or ''
    if not name:
        raise NotFound()

    # ── Price series ──────────────────────────────────────────────────────────
    series = []
    try:
        hist = hist_fut.result()
        if not hist.empty:
            for ts, row in hist.iterrows():
                c = safe_float(row.get('Close'))
                v = safe_float(row.get('Volume'), 0)
                if c:
                    series.append({
                        'd': ts.strftime('%Y-%m-%d'),
                        'p': round(c, 2),
                        'v': int(v or 0),
                    })
    except Exception as e:
        logger.error(f'History failed: {e}')

    # ── Financials ────────────────────────────────────────────────────────────
    fin = []
    try:
        fin = fin_fut.result()
    except Exception as e:
        logger.error(f'Financials failed: {e}')

    peers = peers_fut.result()

    # ── Stats from info ───────────────────────────────────────────────────────
    recent = fin[0] if fin else {}
    mktcap = safe_float(info.get('marketCap'))
    price  = safe_float(info.get('currentPrice') or info.get('regularMarketPrice'))
    mktcap_bn = (mktcap or 0) / 1e9

    pe  = fmt_num(info.get('trailingPE'), 1)
    pb  = fmt_num(info.get('priceToBook'), 1)
    ps  = fmt_num(info.get('priceToSalesTrailing12Months'), 1)
    ev_ebitda = fmt_num(info.get('enterpriseToEbitda'), 1)

    # Compute P/E, P/B, P/S from financials if yfinance info doesn't have them
    if pe == '—' and price and recent.get('eps'):
        pe = fmt_num(price / recent['eps'], 1)
    if pb == '—' and mktcap_bn and recent.get('equity'):
        pb = fmt_num(mktcap_bn / recent['equity'], 1)
    if ps == '—' and mktcap_bn and recent.get('rev'):
        ps = fmt_num(mktcap_bn / recent['rev'], 1)

    curr_ratio = fmt_num(info.get('currentRatio'), 2)
    de_ratio   = fmt_num(info.get('debtToEquity'), 2) if info.get('debtToEquity') else '—'
    # Compute interest coverage from financials if available
    int_cov = '—'
    if recent.get('ebitda') and recent.get('int_exp') and recent['int_exp'] != 0:
        int_cov = fmt_num(recent['ebitda'] / abs(recent['int_exp']), 2)

    # Smoothed market cap
    shares_out = safe_float(info.get('sharesOutstanding'))
    smoothed_mcap = '—'
    if series and shares_out:
        window = series[-252:]
        avg_price = sum(d['p'] for d in window) / len(window)
        smoothed_mcap = fmt_cap(avg_price * shares_out)

    # Jurisdiction
    country   = info.get('country') or 'US'
    state_raw = info.get('state') or info.get('stateOfIncorporation') or ''
    jurisdiction = (STATE_MAP.get(str(state_raw).upper().strip(), state_raw) or '—') \
                   if country.upper() in ('US', 'USA', 'UNITED STATES') else country

    # IPO year — FMP profile is most accurate, fast_info as fallback.
    # No series-date fallback: better to show blank than a misleading value.
    ipo_year = ipo_fut.result() or '—'
    if ipo_year == '—':
        try:
            ftd = ticker.fast_info.first_trade_date
            if ftd:
                ipo_year = str(ftd.year)
        except Exception:
            pass

    # 52-week range
    hi = safe_float(info.get('fiftyTwoWeekHigh'))
    lo = safe_float(info.get('fiftyTwoWeekLow'))
    range_52w = f'{fmt_cap(lo)} – {fmt_cap(hi)}' if hi and lo else '—'

    return {
        'as_of':        datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        'data_source':  'yahoo_finance',
        'ticker':       sym,
        'name':         name,
        'sector':       info.get('sector') or '—',
        'industry':     info.get('industry') or '—',
        'exchange':     info.get('exchange') or '—',
        'country':      country,
        'jurisdiction': jurisdiction,
        'ipo_year':     ipo_year,
        'biz':          info.get('longBusinessSummary') or '',
        'image':        '',
        'current_price': price or 0,
        'price_change':  safe_float(info.get('regularMarketChange')) or 0,
        'range_52w':    range_52w,
        'series':       series,
        'stats': {
            'mcap':          fmt_cap(mktcap),
            'smoothed_mcap': smoothed_mcap,
            'pe':            pe,
            'pb':            pb,
            'ps':            ps,
            'ev_ebitda':     ev_ebitda,
            'shares':        fmt_count(shares_out),
            'avg_vol':       fmt_count(info.get('averageVolume') or info.get('averageVolume10Day')),
            'days_to_cover': fmt_num(info.get('shortRatio'), 2),
            'shares_short':  fmt_count(info.get('sharesShort')),
            'curr_ratio':    f'{curr_ratio}x' if curr_ratio != '—' else '—',
            'de_ratio':      de_ratio,
            'int_cov':       f'{int_cov}x' if int_cov != '—' else '—',
        },
        'fin':   fin,
        'peers': peers,
    }

def fetch_financials(ticker):
    """Extract 3 years of annual financials from yfinance DataFrames."""
    inc = ticker.income_stmt
    bal = ticker.balance_sheet
    cf  = ticker.cashflow

    # Determine fiscal years from income statement columns
    if inc is None or inc.empty:
        return []

    fin = []
    for i, col in enumerate(inc.columns[:3]):
        yr = str(col.year)[-2:] if hasattr(col, 'year') else str(col)[-2:]

        # Income statement — column-specific lookup (df_val scans all columns, use this instead)
        def inc_val(*names):
            for name in names:
                if name in inc.index:
                    v = safe_float(inc.loc[name, col])
                    if v is not None:
                        return v
            return None

        rev = bn(inc_val('Total Revenue', 'Revenue'))
        ni  = bn(inc_val('Net Income', 'Net Income Common Stockholders'))
        eps_raw = inc_val('Diluted EPS', 'Basic EPS')
        eps = round(float(eps_raw), 2) if eps_raw else None
        op_income = inc_val('Operating Income', 'EBIT')
        da = inc_val('Depreciation And Amortization', 'Reconciled Depreciation')
        ebitda = bn((op_income or 0) + (da or 0)) if op_income else bn(inc_val('EBITDA', 'Normalized EBITDA'))
        int_exp_raw = inc_val('Interest Expense', 'Interest Expense Non Operating')
        int_exp = bn(int_exp_raw)

        # Balance sheet (column index may differ)
        def bal_val(*names):
            if bal is None or bal.empty or i >= len(bal.columns):
                return None
            col_b = bal.columns[i]
            for name in names:
                if name in bal.index:
                    v = safe_float(bal.loc[name, col_b])
                    if v is not None:
                        return v
            return None

        assets_v   = bn(bal_val('Total Assets'))
        cash_v     = bn(bal_val('Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments'))
        debt_v     = bn(bal_val('Total Debt', 'Long Term Debt'))
        equity_v   = bn(bal_val('Stockholders Equity', 'Common Stock Equity'))
        goodwill_v = bn(bal_val('Goodwill', 'Goodwill And Other Intangible Assets'))
        curr_a     = bn(bal_val('Current Assets'))
        curr_l     = bn(bal_val('Current Liabilities'))
        gw_pct     = round(goodwill_v / assets_v * 100, 1) if goodwill_v and assets_v else None

        # Cash flow
        def cf_val(*names):
            if cf is None or cf.empty or i >= len(cf.columns):
                return None
            col_c = cf.columns[i]
            for name in names:
                if name in cf.index:
                    v = safe_float(cf.loc[name, col_c])
                    if v is not None:
                        return v
            return None

        op_cf = bn(cf_val('Operating Cash Flow', 'Cash Flow From Continuing Operating Activities'))

        fin.append({
            'yr':         f'FY{yr}',
            'rev':        rev,
            'ni':         ni,
            'eps':        eps,
            'ebitda':     ebitda,
            'assets':     assets_v,
            'cash':       cash_v,
            'op_cf':      op_cf,
            'total_debt': debt_v,
            'goodwill':   goodwill_v,
            'gw_pct':     gw_pct,
            'curr_assets': curr_a,
            'curr_liab':  curr_l,
            'int_exp':    int_exp,
            'equity':     equity_v,
        })

    return fin
