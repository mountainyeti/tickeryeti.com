import json
import os
import re
import urllib.request
import urllib.error
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

FMP_BASE = 'https://financialmodelingprep.com/stable'
FMP_KEY  = os.environ['FMP_KEY']

CORS = {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Content-Type': 'application/json',
}

def lambda_handler(event, context):
    method = (event.get('requestContext') or {}).get('http', {}).get('method', 'GET')
    if method == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS, 'body': ''}

    params = event.get('queryStringParameters') or {}
    sym = (params.get('ticker') or '').upper().strip()

    if not sym or not re.match(r'^[A-Z0-9.\-]{1,10}$', sym):
        return err(400, 'Invalid ticker symbol')

    try:
        data = build_response(sym)
        return {'statusCode': 200, 'headers': CORS, 'body': json.dumps(data)}
    except NotFound:
        return err(404, f'No data found for {sym}')
    except Exception as e:
        return err(500, str(e))

def err(code, msg):
    return {'statusCode': code, 'headers': CORS, 'body': json.dumps({'error': msg})}

class NotFound(Exception):
    pass

# ── FMP fetch ──────────────────────────────────────────────────────────────────

def fmp(path):
    sep = '&' if '?' in path else '?'
    url = f'{FMP_BASE}{path}{sep}apikey={FMP_KEY}'
    req = urllib.request.Request(url, headers={'User-Agent': 'tickeryeti/1.0'})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read())

def fetch_all(sym):
    calls = {
        'profile':  f'/profile?symbol={sym}',
        'history':  f'/historical-price-eod/light?symbol={sym}&limit=2520',
        'income':   f'/income-statement?symbol={sym}&limit=3',
        'balance':  f'/balance-sheet-statement?symbol={sym}&limit=3',
        'cashflow': f'/cash-flow-statement?symbol={sym}&limit=3',
        'metrics':  f'/key-metrics?symbol={sym}&limit=1',
        'ratios':   f'/ratios?symbol={sym}&limit=1',
        'peers':    f'/stock-peers?symbol={sym}',
    }
    out = {}
    with ThreadPoolExecutor(max_workers=7) as ex:
        futs = {ex.submit(fmp, path): name for name, path in calls.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                out[name] = fut.result()
            except Exception as e:
                logger.error(f"FMP {name} failed: {type(e).__name__}: {e}")
                out[name] = None
    return out

# ── Helpers ────────────────────────────────────────────────────────────────────

def safe(v, scale=1.0, dp=2):
    try:
        f = float(v) * scale
        return round(f, dp) if f != 0 else None
    except (TypeError, ValueError):
        return None

def fmt_cap(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return '—'
    if v == 0: return '—'
    if abs(v) >= 1e12: return f'${v/1e12:.2f}T'
    if abs(v) >= 1e9:  return f'${v/1e9:.2f}B'
    if abs(v) >= 1e6:  return f'${v/1e6:.2f}M'
    return f'${v:,.0f}'

def fmt_count(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return '—'
    if v == 0: return '—'
    if abs(v) >= 1e9: return f'{v/1e9:.2f}B'
    if abs(v) >= 1e6: return f'{v/1e6:.2f}M'
    return f'{v:,.0f}'

def fmt_num(v, dp=2):
    x = safe(v, 1, dp)
    return str(x) if x is not None else '—'

def fmt_pct(v):
    x = safe(v, 100, 1)
    return f'{x}%' if x is not None else '—'

# ── Main builder ───────────────────────────────────────────────────────────────

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

def build_response(sym):
    raw = fetch_all(sym)

    profile  = (raw.get('profile')  or [{}])[0]
    hist_raw = raw.get('history') or []
    income   = raw.get('income')   or []
    balance  = raw.get('balance')  or []
    cashflow = raw.get('cashflow') or []
    metrics  = (raw.get('metrics') or [{}])[0]
    ratios   = (raw.get('ratios')  or [{}])[0]
    peers_raw = raw.get('peers')   or []

    if not profile.get('companyName'):
        raise NotFound()

    # ── Price series (chronological) ──────────────────────────────────────────
    series = []
    for h in reversed(hist_raw):
        p = h.get('price') or h.get('adjClose') or h.get('close')
        v = h.get('volume', 0)
        if p:
            series.append({'d': h['date'], 'p': round(float(p), 2), 'v': int(v or 0)})

    # ── Financial years ───────────────────────────────────────────────────────
    fin = []
    for i in range(min(3, max(len(income), len(balance), len(cashflow)))):
        inc = income[i]  if i < len(income)   else {}
        bal = balance[i] if i < len(balance)  else {}
        cf  = cashflow[i] if i < len(cashflow) else {}

        yr = (inc.get('fiscalYear') or inc.get('calendarYear') or
              str(inc.get('date', ''))[:4] or
              str(bal.get('date', ''))[:4] or '—')

        ebitda_v   = safe(inc.get('ebitda') or inc.get('operatingIncome'), 1e-9)
        int_exp_v  = safe(inc.get('interestExpense'), 1e-9)
        curr_ast_v = safe(bal.get('totalCurrentAssets'), 1e-9)
        curr_lib_v = safe(bal.get('totalCurrentLiabilities'), 1e-9)
        equity_v   = safe(bal.get('totalStockholdersEquity') or bal.get('totalEquity'), 1e-9)
        debt_v     = safe(bal.get('totalDebt') or bal.get('longTermDebt'), 1e-9)
        assets_v   = safe(bal.get('totalAssets'), 1e-9)
        goodwill_v = safe(bal.get('goodwill') or bal.get('goodwillAndIntangibleAssets'), 1e-9)
        gw_pct     = round(goodwill_v / assets_v * 100, 1) if goodwill_v and assets_v else None

        fin.append({
            'yr':        f"FY{str(yr)[-2:]}",
            'rev':       safe(inc.get('revenue'), 1e-9),
            'ni':        safe(inc.get('netIncome'), 1e-9),
            'eps':       safe(inc.get('epsdiluted'), 1, 2),
            'ebitda':    ebitda_v,
            'assets':    assets_v,
            'cash':      safe(bal.get('cashAndShortTermInvestments') or bal.get('cashAndCashEquivalents'), 1e-9),
            'op_cf':     safe(cf.get('operatingCashFlow'), 1e-9),
            'total_debt': debt_v,
            'goodwill':  goodwill_v,
            'gw_pct':    gw_pct,
            'curr_assets': curr_ast_v,
            'curr_liab': curr_lib_v,
            'int_exp':   int_exp_v,
            'equity':    equity_v,
        })

    # ── Derived ratios (most recent year) ──────────────────────────────────────
    recent = fin[0] if fin else {}
    curr_ratio   = round(recent['curr_assets'] / recent['curr_liab'], 2) if (recent.get('curr_assets') and recent.get('curr_liab')) else None
    de_ratio     = round(recent['total_debt'] / recent['equity'], 2)     if (recent.get('total_debt') and recent.get('equity'))    else None
    int_cov      = round(recent['ebitda'] / abs(recent['int_exp']), 2)   if (recent.get('ebitda') and recent.get('int_exp') and recent['int_exp'] != 0) else None

    # ── Stats ─────────────────────────────────────────────────────────────────
    mktcap   = profile.get('marketCap') or profile.get('mktCap') or metrics.get('marketCap')
    country  = profile.get('country') or 'US'
    state_raw = profile.get('state') or profile.get('stateOfIncorporation') or ''
    if country.upper() in ('US', 'USA', 'UNITED STATES'):
        jurisdiction = STATE_MAP.get(str(state_raw).upper().strip(), state_raw) or '—'
    else:
        jurisdiction = country

    ipo_year = str(profile.get('ipoDate') or '')[:4] or '—'

    # Smoothed market cap: average of 252 most recent daily close × shares
    price_now = profile.get('price') or 0
    shares = profile.get('sharesOutstanding') or (float(mktcap) / float(price_now) if mktcap and price_now else 0)
    smoothed_mcap = None
    if series and shares:
        window = series[-252:]
        smoothed_mcap = fmt_cap(sum(d['p'] for d in window) / len(window) * float(shares or 0))

    # ── Peers ─────────────────────────────────────────────────────────────────
    peers = []
    if isinstance(peers_raw, list) and peers_raw:
        first = peers_raw[0]
        # stable endpoint returns [{symbol, companyName, price, mktCap}, ...]
        if isinstance(first, dict) and 'symbol' in first:
            peers = [p['symbol'] for p in peers_raw if p.get('symbol') != sym][:8]
        else:
            peers = (first.get('peersList') or [])[:8]

    return {
        'as_of':        datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        'ticker':       sym,
        'name':         profile.get('companyName') or sym,
        'sector':       profile.get('sector') or '—',
        'industry':     profile.get('industry') or '—',
        'exchange':     profile.get('exchange') or profile.get('exchangeShortName') or '—',
        'country':      country,
        'jurisdiction': jurisdiction,
        'ipo_year':     ipo_year,
        'biz':          profile.get('description') or '',
        'image':        profile.get('image') or '',
        'current_price': float(profile.get('price') or 0),
        'price_change':  float(profile.get('changes') or 0),
        'range_52w':    profile.get('range') or '—',
        'series':       series,
        'stats': {
            'mcap':         fmt_cap(mktcap),
            'smoothed_mcap': smoothed_mcap or '—',
            'pe':           fmt_num(ratios.get('priceToEarningsRatio'), 1),
            'pb':           fmt_num(ratios.get('priceToBookRatio'), 1),
            'ps':           fmt_num(ratios.get('priceToSalesRatio'), 1),
            'ev_ebitda':    fmt_num(metrics.get('evToEBITDA'), 1),
            'shares':       fmt_count(profile.get('sharesOutstanding') or (float(mktcap)/float(profile.get('price')) if mktcap and profile.get('price') else None)),
            'avg_vol':      fmt_count(profile.get('averageVolume') or profile.get('volAvg')),
            'days_to_cover': '—',
            'shares_short':  '—',
            'curr_ratio':   f'{curr_ratio}x' if curr_ratio else '—',
            'de_ratio':     str(de_ratio) if de_ratio else '—',
            'int_cov':      f'{int_cov}x' if int_cov else '—',
        },
        'fin':   fin,
        'peers': peers,
    }
