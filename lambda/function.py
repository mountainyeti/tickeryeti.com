import json
import os
import re
import urllib.request
import urllib.error
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, date

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

PREMIUM = '__PREMIUM__'

# ── Entry ──────────────────────────────────────────────────────────────────────

def lambda_handler(event, context):
    method = (event.get('requestContext') or {}).get('http', {}).get('method', 'GET')
    if method == 'OPTIONS':
        return {'statusCode': 200, 'headers': CORS, 'body': ''}
    params = event.get('queryStringParameters') or {}
    sym = (params.get('ticker') or '').upper().strip()
    if not sym or not re.match(r'^[A-Z0-9.\-]{1,10}$', sym):
        return err(400, 'Invalid ticker symbol')
    try:
        return {'statusCode': 200, 'headers': CORS, 'body': json.dumps(build_response(sym))}
    except NotFound:
        return err(404, f'No data found for {sym}')
    except Exception as e:
        logger.exception('Unhandled error')
        return err(500, str(e))

def err(code, msg):
    return {'statusCode': code, 'headers': CORS, 'body': json.dumps({'error': msg})}

class NotFound(Exception):
    pass

# ── FMP ────────────────────────────────────────────────────────────────────────

def fmp(path):
    sep = '&' if '?' in path else '?'
    req = urllib.request.Request(f'{FMP_BASE}{path}{sep}apikey={FMP_KEY}',
                                 headers={'User-Agent': 'tickeryeti/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 402:
            return PREMIUM
        raise

def fetch_all_fmp(sym):
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
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fmp, path): name for name, path in calls.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                out[name] = fut.result()
            except Exception as e:
                logger.error(f'FMP {name}: {type(e).__name__}: {e}')
                out[name] = None
    return out


# ── SEC EDGAR financials ───────────────────────────────────────────────────────

# Concept priority lists — try each until one has data
_EDGAR_MAP = {
    'rev':        ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 'RevenueFromContractWithCustomerIncludingAssessedTax'],
    'ni':         ['NetIncomeLoss', 'NetIncomeLossAttributableToParent'],
    'eps':        ['EarningsPerShareDiluted', 'EarningsPerShareBasic'],
    'assets':     ['Assets'],
    'curr_assets':['AssetsCurrent'],
    'curr_liab':  ['LiabilitiesCurrent'],
    'equity':     ['StockholdersEquity', 'StockholdersEquityAttributableToParent'],
    'lt_debt':    ['LongTermDebt', 'LongTermDebtNoncurrent'],
    'st_debt':    ['DebtCurrent', 'ShortTermBorrowings', 'LongTermDebtCurrent'],
    'cash':       ['CashAndCashEquivalentsAtCarryingValue', 'CashAndCashEquivalents'],
    'goodwill':   ['Goodwill'],
    'op_cf':      ['NetCashProvidedByUsedInOperatingActivities'],
    'op_income':  ['OperatingIncomeLoss'],
    'da':         ['DepreciationDepletionAndAmortization', 'DepreciationAndAmortization'],
    'int_exp':    ['InterestExpense', 'InterestExpenseDebt', 'InterestAndDebtExpense'],
}

def edgar_annual(facts_usgaap, *concept_names):
    """Aggregate FY annual values across ALL concept names, return 3 most recent years.
    Companies switch XBRL concepts over time (e.g. Revenues -> RevenueFromContract...),
    so we merge across all matching concepts and take the most recent 3 years."""
    all_by_yr = {}
    for name in concept_names:
        concept = facts_usgaap.get(name)
        if not concept:
            continue
        units = concept.get('units', {})
        entries = (units.get('USD') or units.get('USD/shares') or
                   units.get('shares') or [])
        for e in entries:
            if e.get('form') not in ('10-K', '10-K/A') or e.get('fp') != 'FY':
                continue
            fy = str(e.get('fy') or str(e.get('end', ''))[:4])
            if fy and fy.isdigit() and int(fy) > 2000:
                if fy not in all_by_yr or e.get('filed', '') > all_by_yr[fy].get('filed', ''):
                    all_by_yr[fy] = e
    sorted_yrs = sorted(all_by_yr.keys(), key=lambda x: int(x), reverse=True)[:3]
    return [{'yr': y, 'val': all_by_yr[y]['val']} for y in sorted_yrs]

def edgar_financials(cik):
    """Fetch 3 years of annual financial data from SEC EDGAR."""
    cik_str = str(int(cik)).zfill(10)
    url = f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_str}.json'
    req = urllib.request.Request(url, headers={'User-Agent': 'TickerYeti admin@tickeryeti.com'})
    with urllib.request.urlopen(req, timeout=20) as r:
        facts = json.loads(r.read()).get('facts', {}).get('us-gaap', {})

    def get3(key):
        return edgar_annual(facts, *_EDGAR_MAP.get(key, [key]))

    rev_r   = get3('rev');    ni_r  = get3('ni');   eps_r = get3('eps')
    ast_r   = get3('assets'); ca_r  = get3('curr_assets'); cl_r = get3('curr_liab')
    eq_r    = get3('equity'); ltd_r = get3('lt_debt'); std_r = get3('st_debt')
    cash_r  = get3('cash');   gw_r  = get3('goodwill')
    cf_r    = get3('op_cf');  oi_r  = get3('op_income'); da_r = get3('da')
    ie_r    = get3('int_exp')

    # Build indexed lookup by fiscal year
    def by_yr(records): return {r['yr']: r['val'] for r in records}

    rev_d  = by_yr(rev_r);  ni_d  = by_yr(ni_r);   eps_d = by_yr(eps_r)
    ast_d  = by_yr(ast_r);  ca_d  = by_yr(ca_r);   cl_d  = by_yr(cl_r)
    eq_d   = by_yr(eq_r);   ltd_d = by_yr(ltd_r);  std_d = by_yr(std_r)
    cash_d = by_yr(cash_r); gw_d  = by_yr(gw_r);   cf_d  = by_yr(cf_r)
    oi_d   = by_yr(oi_r);   da_d  = by_yr(da_r);   ie_d  = by_yr(ie_r)

    # Determine the 3 most recent years that have revenue data
    years = sorted(rev_d.keys(), reverse=True)[:3]
    if not years:
        years = sorted(ast_d.keys(), reverse=True)[:3]

    fin = []
    for yr in years:
        def bn(d):  # convert raw dollars → $B, return None if missing
            v = d.get(yr)
            return round(float(v) / 1e9, 2) if v is not None else None

        lt_d_v = bn(ltd_d); st_d_v = bn(std_d)
        total_debt = round(lt_d_v + (st_d_v or 0), 2) if lt_d_v is not None else st_d_v

        assets_v   = bn(ast_d)
        goodwill_v = bn(gw_d)
        gw_pct     = round(goodwill_v / assets_v * 100, 1) if goodwill_v and assets_v else None

        oi_v = bn(oi_d); da_v = bn(da_d)
        ebitda_v = round(oi_v + (da_v or 0), 2) if oi_v is not None else None

        eps_raw = eps_d.get(yr)
        eps_v   = round(float(eps_raw), 2) if eps_raw is not None else None

        curr_a = bn(ca_d); curr_l = bn(cl_d)
        equity_v = bn(eq_d); int_exp_v = bn(ie_d)

        fin.append({
            'yr':         f'FY{str(yr)[-2:]}',
            'rev':        bn(rev_d),
            'ni':         bn(ni_d),
            'eps':        eps_v,
            'ebitda':     ebitda_v,
            'assets':     assets_v,
            'cash':       bn(cash_d),
            'op_cf':      bn(cf_d),
            'total_debt': total_debt,
            'goodwill':   goodwill_v,
            'gw_pct':     gw_pct,
            'curr_assets': curr_a,
            'curr_liab':  curr_l,
            'int_exp':    int_exp_v,
            'equity':     equity_v,
        })
    return fin

# ── Helpers ────────────────────────────────────────────────────────────────────

def safe(v, scale=1.0, dp=2):
    try:
        f = float(v) * scale
        return round(f, dp) if f != 0 else None
    except (TypeError, ValueError):
        return None

def fmt_cap(v):
    try: v = float(v)
    except (TypeError, ValueError): return '—'
    if v == 0: return '—'
    if abs(v) >= 1e12: return f'${v/1e12:.2f}T'
    if abs(v) >= 1e9:  return f'${v/1e9:.2f}B'
    if abs(v) >= 1e6:  return f'${v/1e6:.2f}M'
    return f'${v:,.0f}'

def fmt_count(v):
    try: v = float(v)
    except (TypeError, ValueError): return '—'
    if v == 0: return '—'
    if abs(v) >= 1e9: return f'{v/1e9:.2f}B'
    if abs(v) >= 1e6: return f'{v/1e6:.2f}M'
    return f'{v:,.0f}'

def fmt_num(v, dp=2):
    x = safe(v, 1, dp)
    return str(x) if x is not None else '—'

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

# ── Main ───────────────────────────────────────────────────────────────────────

def build_response(sym):
    raw = fetch_all_fmp(sym)

    profile_list = raw.get('profile')
    profile = (profile_list[0] if isinstance(profile_list, list) and profile_list else {})
    if not profile.get('companyName'):
        raise NotFound()

    peers_raw = raw.get('peers') or []
    needs_alt = (raw.get('history') is PREMIUM or not raw.get('history') or
                 raw.get('income')  is PREMIUM or not raw.get('income'))

    # ── Price series ──────────────────────────────────────────────────────────
    # For non-FMP tickers, return empty series — the browser fetches chart from Yahoo Finance directly
    if needs_alt:
        logger.info(f'FMP premium for {sym} — using EDGAR for financials, browser handles chart')
        series = []
    else:
        hist_raw = raw.get('history') or []
        series = []
        for h in reversed(hist_raw):
            p = h.get('price') or h.get('adjClose') or h.get('close')
            if p:
                series.append({'d': h['date'], 'p': round(float(p), 2), 'v': int(h.get('volume', 0) or 0)})

    # ── Financials ────────────────────────────────────────────────────────────
    if needs_alt:
        cik = profile.get('cik')
        fin = []
        if cik:
            try:
                fin = edgar_financials(cik)
            except Exception as e:
                logger.error(f'EDGAR failed for CIK {cik}: {e}')
        if not fin:
            # EDGAR failed — parse FMP income/balance/cashflow if available
            income   = [x for x in (raw.get('income')   or []) if x is not PREMIUM] or []
            balance  = [x for x in (raw.get('balance')  or []) if x is not PREMIUM] or []
            cashflow = [x for x in (raw.get('cashflow') or []) if x is not PREMIUM] or []
            fin = _parse_fmp_fin(income, balance, cashflow)
    else:
        fin = _parse_fmp_fin(
            raw.get('income') or [],
            raw.get('balance') or [],
            raw.get('cashflow') or [],
        )

    # ── Ratios ────────────────────────────────────────────────────────────────
    def unlist(key):
        v = raw.get(key)
        if v is PREMIUM or not isinstance(v, list) or not v: return {}
        return v[0] if isinstance(v[0], dict) else {}

    fmp_ratios  = unlist('ratios')
    fmp_metrics = unlist('metrics')

    recent   = fin[0] if fin else {}
    mktcap   = profile.get('marketCap') or profile.get('mktCap') or fmp_metrics.get('marketCap')
    price_now = float(profile.get('price') or 0)
    mktcap_bn = float(mktcap or 0) / 1e9

    # P/E: FMP ratios → compute from price/EPS
    pe_raw = fmp_ratios.get('priceToEarningsRatio')
    if not pe_raw and recent.get('eps') and price_now:
        pe_raw = round(price_now / recent['eps'], 1)
    # P/B: FMP ratios → compute from market cap / equity
    pb_raw = fmp_ratios.get('priceToBookRatio')
    if not pb_raw and recent.get('equity') and mktcap_bn:
        pb_raw = round(mktcap_bn / recent['equity'], 1)
    # P/S: FMP ratios → compute from market cap / revenue
    ps_raw = fmp_ratios.get('priceToSalesRatio')
    if not ps_raw and recent.get('rev') and mktcap_bn:
        ps_raw = round(mktcap_bn / recent['rev'], 1)

    curr_ratio = round(recent['curr_assets'] / recent['curr_liab'], 2) if (recent.get('curr_assets') and recent.get('curr_liab')) else None
    de_ratio   = round(recent['total_debt'] / recent['equity'], 2)     if (recent.get('total_debt')  and recent.get('equity'))    else None
    int_cov    = round(recent['ebitda'] / abs(recent['int_exp']), 2)   if (recent.get('ebitda') and recent.get('int_exp') and recent['int_exp'] != 0) else None

    # ── Company meta ──────────────────────────────────────────────────────────
    country   = profile.get('country') or 'US'
    state_raw = profile.get('state') or ''
    jurisdiction = (STATE_MAP.get(str(state_raw).upper().strip(), state_raw) or '—') \
                   if country.upper() in ('US', 'USA', 'UNITED STATES') else country
    shares_out = profile.get('sharesOutstanding') or (float(mktcap) / price_now if mktcap and price_now else None)
    smoothed_mcap = None
    if series and shares_out:
        w = series[-252:]
        smoothed_mcap = fmt_cap(sum(d['p'] for d in w) / len(w) * float(shares_out))

    # ── Peers ─────────────────────────────────────────────────────────────────
    peers = []
    if isinstance(peers_raw, list) and peers_raw and peers_raw is not PREMIUM:
        first = peers_raw[0]
        if isinstance(first, dict) and 'symbol' in first:
            peers = [p['symbol'] for p in peers_raw if p.get('symbol') != sym][:8]
        elif isinstance(first, dict):
            peers = (first.get('peersList') or [])[:8]

    return {
        'as_of':        datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        'data_source':  'stooq+edgar' if needs_alt else 'fmp',
        'ticker':       sym,
        'name':         profile.get('companyName') or sym,
        'sector':       profile.get('sector') or '—',
        'industry':     profile.get('industry') or '—',
        'exchange':     profile.get('exchange') or profile.get('exchangeShortName') or '—',
        'country':      country,
        'jurisdiction': jurisdiction,
        'ipo_year':     str(profile.get('ipoDate') or '')[:4] or '—',
        'biz':          profile.get('description') or '',
        'image':        profile.get('image') or '',
        'current_price': price_now,
        'price_change':  float(profile.get('changes') or 0),
        'range_52w':    profile.get('range') or '—',
        'series':       series,
        'stats': {
            'mcap':          fmt_cap(mktcap),
            'smoothed_mcap': smoothed_mcap or '—',
            'pe':            fmt_num(pe_raw, 1),
            'pb':            fmt_num(pb_raw, 1),
            'ps':            fmt_num(ps_raw, 1),
            'ev_ebitda':     fmt_num(fmp_metrics.get('evToEBITDA'), 1),
            'shares':        fmt_count(shares_out),
            'avg_vol':       fmt_count(profile.get('averageVolume') or profile.get('volAvg')),
            'days_to_cover': '—',
            'shares_short':  '—',
            'curr_ratio':    f'{curr_ratio}x' if curr_ratio else '—',
            'de_ratio':      str(de_ratio) if de_ratio else '—',
            'int_cov':       f'{int_cov}x' if int_cov else '—',
        },
        'fin':   fin,
        'peers': peers,
    }

def _parse_fmp_fin(income, balance, cashflow):
    fin = []
    for i in range(min(3, max(len(income), len(balance), len(cashflow)))):
        inc = income[i]  if i < len(income)   else {}
        bal = balance[i] if i < len(balance)  else {}
        cf  = cashflow[i] if i < len(cashflow) else {}
        yr  = (inc.get('fiscalYear') or str(inc.get('date', ''))[:4] or
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
            'yr': f'FY{str(yr)[-2:]}',
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
    return fin
