// ============================================================
// CONFIG
// ============================================================

const API_BASE = 'https://nlhh3rlzh9.execute-api.us-west-2.amazonaws.com';

const TY_SITES = [
  { id: 'yahoo',   label: 'Yahoo Finance', url: t => `https://finance.yahoo.com/quote/${t}` },
  { id: 'seeking', label: 'Seeking Alpha', url: t => `https://seekingalpha.com/symbol/${t}/earnings` },
  { id: 'edgar',   label: 'SEC EDGAR',     url: t => `https://www.sec.gov/cgi-bin/browse-edgar?CIK=${t}&owner=exclude&action=getcompany` },
  { id: 'finviz',  label: 'Finviz',        url: t => `https://finviz.com/quote.ashx?t=${t}` },
];

// ============================================================
// APP STATE
// ============================================================

const state = {
  company: null,
  range: '1y',
  checks: { yahoo: true, seeking: true, edgar: true, finviz: true },
};

// ============================================================
// API
// ============================================================

async function fetchTicker(ticker) {
  const res = await fetch(`${API_BASE}/?ticker=${encodeURIComponent(ticker)}`);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  // If Lambda didn't return price history (FMP premium ticker), fetch chart from
  // Yahoo Finance directly from the browser — works fine from user IPs.
  if (!data.series || data.series.length === 0) {
    try {
      data.series = await fetchYFChart(ticker);
    } catch (e) {
      console.warn('YF chart fallback failed:', e.message);
    }
  }
  return data;
}

async function fetchYFChart(ticker) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?interval=1d&range=10y&includeAdjustedClose=true`;
  const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
  if (!res.ok) throw new Error(`Yahoo Finance ${res.status}`);
  const json = await res.json();
  const result = json.chart?.result?.[0];
  if (!result) return [];
  const ts      = result.timestamp || [];
  const closes  = result.indicators?.adjclose?.[0]?.adjclose || result.indicators?.quote?.[0]?.close || [];
  const volumes = result.indicators?.quote?.[0]?.volume || [];
  return ts.map((t, i) => ({
    d: new Date(t * 1000).toISOString().slice(0, 10),
    p: closes[i] != null ? Math.round(closes[i] * 100) / 100 : null,
    v: volumes[i] || 0,
  })).filter(pt => pt.p !== null);
}

// ============================================================
// FORMATTERS
// ============================================================

function fmtPrice(p) {
  if (p == null || p === 0) return '—';
  return '$' + Number(p).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function fmtBn(v) {
  if (v == null) return '—';
  if (Math.abs(v) >= 1000) return '$' + (v / 1000).toFixed(1) + 'T'; // v is already in $B
  if (Math.abs(v) >= 1)    return '$' + v.toFixed(1) + 'B';
  return '$' + (v * 1000).toFixed(0) + 'M';
}
function fmtPct(p) {
  if (p == null) return '—';
  return (p >= 0 ? '+' : '') + p.toFixed(2) + '%';
}
function fmtDate(s) {
  const d = new Date(s + 'T00:00:00');
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

// ============================================================
// RECENT TICKERS
// ============================================================

function getRecent() {
  try {
    const s = JSON.parse(localStorage.getItem('ty_recent') || '[]');
    return s.length ? s : ['AAPL', 'NVDA', 'MSFT', 'TSLA'];
  } catch { return ['AAPL', 'NVDA', 'MSFT', 'TSLA']; }
}

function addRecent(t) {
  try {
    const r = JSON.parse(localStorage.getItem('ty_recent') || '[]');
    localStorage.setItem('ty_recent', JSON.stringify([t, ...r.filter(x => x !== t)].slice(0, 6)));
  } catch {}
}

function renderRecent() {
  const row = document.getElementById('ty-recent-row');
  row.innerHTML =
    '<span style="font-size:11px;text-transform:uppercase;letter-spacing:0.14em;opacity:0.8">Recent</span>' +
    getRecent().map(t =>
      `<button type="button" class="ty-peer" style="padding:5px 12px" data-ticker="${t}">` +
      `<span class="ty-peer-tick">${t}</span></button>`
    ).join('');
  row.querySelectorAll('[data-ticker]').forEach(btn => {
    btn.addEventListener('click', () => loadTicker(btn.dataset.ticker));
  });
}

// ============================================================
// CHART (price line + volume bars)
// ============================================================

function getChartSlice(series, range) {
  const map = { '1y': 252, '2y': 504, '3y': 756, '5y': 1260, '10y': 2520 };
  return series.slice(-Math.min(map[range] || 252, series.length));
}

function renderChart(wrap, series, range) {
  const data = getChartSlice(series, range);
  if (!data.length) { wrap.innerHTML = '<p class="small" style="opacity:.7;padding:20px">No chart data.</p>'; return; }

  const W = 1100, H = 360;
  const PADL = 64, PADR = 18, PADT = 14, PADB = 32;
  const iw = W - PADL - PADR;

  // Split: 70% price, 5% gap, 25% volume
  const ih_total = H - PADT - PADB;
  const ih_price = Math.round(ih_total * 0.70);
  const vol_top  = PADT + ih_price + Math.round(ih_total * 0.05);
  const vol_h    = H - PADB - vol_top;

  let minP = Infinity, maxP = -Infinity, maxV = 0;
  data.forEach(d => {
    if (d.p < minP) minP = d.p;
    if (d.p > maxP) maxP = d.p;
    if (d.v > maxV) maxV = d.v;
  });
  const pad = (maxP - minP) * 0.08 || 1;
  minP -= pad; maxP += pad;

  const xv  = i => PADL + (i / ((data.length - 1) || 1)) * iw;
  const yp  = p => PADT + (1 - (p - minP) / ((maxP - minP) || 1)) * ih_price;
  const barH = v => maxV ? Math.max(1, (v / maxV) * vol_h) : 0;
  const barW = Math.max(1, iw / data.length - 0.5);

  const pts  = data.map((d, i) => (i === 0 ? 'M' : 'L') + xv(i).toFixed(1) + ',' + yp(d.p).toFixed(1)).join(' ');
  const area = pts + ' L' + xv(data.length-1).toFixed(1) + ',' + (PADT+ih_price).toFixed(1) +
               ' L' + xv(0).toFixed(1) + ',' + (PADT+ih_price).toFixed(1) + ' Z';

  const yTicks = Array.from({ length: 5 }, (_, i) => minP + (maxP - minP) * i / 4);
  const seen = new Set(), xTicks = [];
  data.forEach((d, i) => {
    const [yr, mo] = d.d.split('-');
    const key = yr + '-' + mo;
    if (!seen.has(key) && (mo === '01' || mo === '07') && data.length > 60) {
      seen.add(key);
      xTicks.push({ i, label: mo === '01' ? yr : 'Jul ' + yr.slice(-2) });
    }
  });

  wrap.innerHTML =
    `<svg class="ty-chart-svg" id="ty-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">` +
      '<defs>' +
        '<linearGradient id="ty-fill" x1="0" y1="0" x2="0" y2="1">' +
          '<stop offset="0%" stop-color="#fff" stop-opacity="0.32"/>' +
          '<stop offset="100%" stop-color="#fff" stop-opacity="0"/>' +
        '</linearGradient>' +
      '</defs>' +
      // Y-axis gridlines + labels
      yTicks.map(v =>
        `<line x1="${PADL}" x2="${W-PADR}" y1="${yp(v).toFixed(1)}" y2="${yp(v).toFixed(1)}" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>` +
        `<text x="${PADL-8}" y="${(yp(v)+4).toFixed(1)}" text-anchor="end" font-size="11" fill="rgba(255,255,255,0.72)" font-family="Helvetica Neue,Helvetica,Arial,sans-serif">$${v.toFixed(v < 10 ? 2 : 0)}</text>`
      ).join('') +
      // X-axis labels
      xTicks.slice(0, 10).map(t =>
        `<text x="${xv(t.i).toFixed(1)}" y="${H-8}" text-anchor="middle" font-size="11" fill="rgba(255,255,255,0.72)" font-family="Helvetica Neue,Helvetica,Arial,sans-serif">${t.label}</text>`
      ).join('') +
      // Volume bars
      data.map((d, i) => {
        const bh = barH(d.v);
        return `<rect x="${(xv(i) - barW/2).toFixed(1)}" y="${(vol_top + vol_h - bh).toFixed(1)}" width="${barW.toFixed(1)}" height="${bh.toFixed(1)}" fill="rgba(255,255,255,0.22)"/>`;
      }).join('') +
      // Volume divider
      `<line x1="${PADL}" x2="${W-PADR}" y1="${vol_top}" y2="${vol_top}" stroke="rgba(255,255,255,0.12)" stroke-width="1"/>` +
      // Price area fill + line
      `<path d="${area}" fill="url(#ty-fill)"/>` +
      `<path d="${pts}" fill="none" stroke="#fff" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>` +
      // Hover elements
      `<line id="ty-vline" stroke="rgba(255,255,255,0.5)" stroke-dasharray="3 3" style="display:none"/>` +
      `<circle id="ty-dot" r="5" fill="var(--ty-blue)" stroke="#fff" stroke-width="2" style="display:none"/>` +
    '</svg>' +
    '<div id="ty-tip" class="ty-chart-hover" style="display:none">' +
      '<div class="hv-date" id="ty-tip-date"></div>' +
      '<div class="hv-price" id="ty-tip-price"></div>' +
      '<div class="hv-vol" id="ty-tip-vol"></div>' +
    '</div>';

  const svg    = wrap.querySelector('#ty-svg');
  const vline  = wrap.querySelector('#ty-vline');
  const dot    = wrap.querySelector('#ty-dot');
  const tip    = wrap.querySelector('#ty-tip');
  const tipD   = wrap.querySelector('#ty-tip-date');
  const tipP   = wrap.querySelector('#ty-tip-price');
  const tipV   = wrap.querySelector('#ty-tip-vol');

  svg.addEventListener('mousemove', e => {
    const rect = svg.getBoundingClientRect();
    const xPos = ((e.clientX - rect.left) / rect.width) * W;
    const idx  = Math.max(0, Math.min(data.length - 1, Math.round(((xPos - PADL) / iw) * (data.length - 1))));
    const cx   = xv(idx), cy = yp(data[idx].p);

    vline.setAttribute('x1', cx); vline.setAttribute('x2', cx);
    vline.setAttribute('y1', PADT); vline.setAttribute('y2', PADT + ih_price);
    vline.style.display = '';
    dot.setAttribute('cx', cx); dot.setAttribute('cy', cy); dot.style.display = '';

    tip.style.display = '';
    tip.style.left = (cx / W * 100) + '%';
    tip.style.top  = (cy / H * 100) + '%';
    tipD.textContent = fmtDate(data[idx].d);
    tipP.textContent = fmtPrice(data[idx].p);
    tipV.textContent = data[idx].v ? 'Vol: ' + (data[idx].v / 1e6).toFixed(1) + 'M' : '';
  });
  svg.addEventListener('mouseleave', () => {
    vline.style.display = dot.style.display = tip.style.display = 'none';
  });
}

// ============================================================
// DASHBOARD
// ============================================================

function renderDashboard(company) {
  const s    = company.series || [];
  const last = s.length ? s[s.length - 1].p : company.current_price;
  const yrAgo = s.length >= 253 ? s[s.length - 253].p : (s.length ? s[0].p : last);
  const pct  = yrAgo ? (last - yrAgo) / yrAgo * 100 : 0;
  const chgUp = pct >= 0;
  const initials = company.name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();

  // ── Company header ─────────────────────────────────────────────────────────
  const jurLabel = (company.country || '').toUpperCase().includes('US') ? 'State of Inc.' : 'Country';
  document.getElementById('ty-co-col').innerHTML =
    '<div class="d-flex gap-3 align-items-start">' +
      (company.image
        ? `<img src="${company.image}" class="ty-co-logo" style="padding:4px;object-fit:contain" alt="">`
        : `<div class="ty-co-logo">${initials}</div>`) +
      '<div>' +
        `<h2 class="fw-bold mb-1" style="letter-spacing:-0.01em;font-size:26px">${company.name}<span class="ty-ticker-badge">${company.ticker}</span></h2>` +
        '<div class="d-flex flex-wrap gap-2 mb-2">' +
          `<span class="ty-sector-tag"><span class="ty-dot"></span>${company.sector}</span>` +
          `<span class="ty-sector-tag">${company.industry}</span>` +
          `<span class="ty-sector-tag">${company.exchange}</span>` +
          (company.jurisdiction ? `<span class="ty-sector-tag">${jurLabel}: ${company.jurisdiction}</span>` : '') +
          (company.ipo_year && company.ipo_year !== '—' ? `<span class="ty-sector-tag">IPO: ${company.ipo_year}</span>` : '') +
        '</div>' +
        renderBizDesc(company.biz) +
      '</div>' +
    '</div>';

  const srcLabel = company.data_source === 'fmp'
    ? 'Financial Modeling Prep'
    : 'SEC EDGAR · Yahoo Finance';

  document.getElementById('ty-price-col').innerHTML =
    `<div class="ty-price-now">${fmtPrice(last)}</div>` +
    `<div class="ty-price-chg ${chgUp ? 'up' : 'down'}">` +
      `<span class="arrow">${chgUp ? '▲' : '▼'}</span>` +
      `${fmtPrice(Math.abs(last - yrAgo))} (${fmtPct(pct)})` +
    '</div>' +
    `<div class="small mt-1" style="opacity:0.78">1 Year Period Performance</div>` +
    `<div class="small mt-2" style="opacity:0.55">As Of: ${company.as_of || '—'}</div>` +
    `<div class="small" style="opacity:0.55">Data: ${srcLabel}</div>`;

  // ── Chart ──────────────────────────────────────────────────────────────────
  document.getElementById('ty-chart-label').textContent = 'Price · ' + company.ticker;
  renderChart(document.getElementById('ty-chart-wrap'), s, state.range);
  updateRangePerf(company);

  // ── Key Stock Data ─────────────────────────────────────────────────────────
  const st = company.stats || {};
  const stockCards = [
    { label: 'Market Cap',               value: st.mcap,          tip: 'Total market value of all outstanding shares at current price' },
    { label: 'Smoothed Market Cap',      value: st.smoothed_mcap, tip: '12-month rolling daily mean market capitalization' },
    { label: 'Avg Daily Trading Volume', value: st.avg_vol,       tip: 'Average number of shares traded per day over the past 10 days' },
    { label: 'Days to Cover',            value: st.days_to_cover, tip: 'Short interest ratio: shares held short divided by average daily volume. Higher = more days to unwind short positions.' },
    { label: 'Shares Held Short',        value: st.shares_short,  tip: 'Total number of shares currently sold short by investors betting the price will fall' },
    { label: 'Total Shares Outstanding', value: st.shares,        tip: 'Total number of shares issued by the company and held by all shareholders' },
  ];
  document.getElementById('ty-stats-row').innerHTML = stockCards.map(c =>
    '<div class="col-6 col-md-4 col-xl-2">' +
      `<div class="ty-stat" data-tip="${c.tip}">` +
        `<div class="ty-stat-label">${c.label}</div>` +
        `<div class="ty-stat-value">${c.value || '—'}</div>` +
      '</div>' +
    '</div>'
  ).join('');

  // ── Financial table ────────────────────────────────────────────────────────
  renderFinancials(company);

  // ── Key Values ────────────────────────────────────────────────────────────
  document.getElementById('ty-key-values').innerHTML =
    keyValueCard('Current Ratio',     st.curr_ratio, 'Current Assets ÷ Current Liabilities. Below 1.0 means current liabilities exceed current assets.') +
    keyValueCard('Debt / Equity',     st.de_ratio,   'Total Debt ÷ Stockholders Equity. Higher values indicate more financial leverage.') +
    keyValueCard('Interest Coverage', st.int_cov,    'EBITDA ÷ Interest Expense. Shows how easily the company can pay interest on its debt.');

  // ── Valuation Ratios ──────────────────────────────────────────────────────
  document.getElementById('ty-valuation').innerHTML =
    keyValueCard('P/E Ratio', st.pe, 'Price ÷ Earnings Per Share. How much investors pay per dollar of earnings. Lower may indicate undervaluation.') +
    keyValueCard('P/B Ratio', st.pb, 'Price ÷ Book Value Per Share. Compares market price to net asset value. Below 1.0 may indicate undervaluation.') +
    keyValueCard('P/S Ratio', st.ps, 'Price ÷ Sales Per Share (Market Cap ÷ Revenue). Useful for companies with negative earnings.');

  // ── Annual Update ─────────────────────────────────────────────────────────
  document.getElementById('ty-annual-update').innerHTML =
    '<ul class="mb-0" style="padding-left:1.2rem;line-height:1.8">' +
    '<li><strong>Executive &amp; Corporate Governance:</strong> Executed key leadership transitions alongside target board committee refreshment frameworks to strengthen fiduciary tracking.</li>' +
    '<li><strong>Reporting Framework Optimization:</strong> Implemented core segmentation restructures to isolate high-margin operations and provide heightened visibility into capital returns.</li>' +
    '<li><strong>Product Deployment &amp; Strategy:</strong> Expanded addressable markets through deep technical rollouts matched to evolving customer demands.</li>' +
    '<li><strong>Capital Allocation &amp; M&amp;A:</strong> Completed strategic balance sheet adjustments via disciplined transaction activity, including targeted bolt-on additions and non-core divestitures.</li>' +
    '</ul>';

  // ── Peers ─────────────────────────────────────────────────────────────────
  document.getElementById('ty-peers-count').textContent = (company.peers || []).length + ' tickers';
  const peersBody = document.getElementById('ty-peers-body');
  if ((company.peers || []).length) {
    peersBody.innerHTML = '<div class="d-flex flex-wrap gap-2">' +
      company.peers.map(t =>
        `<button class="ty-peer" data-ticker="${t}"><span class="ty-peer-tick">${t}</span></button>`
      ).join('') + '</div>';
    peersBody.querySelectorAll('[data-ticker]').forEach(btn => {
      btn.addEventListener('click', () => loadTicker(btn.dataset.ticker));
    });
  } else {
    peersBody.innerHTML = '<p class="small mb-0" style="opacity:.78">No peers on file. Try Research Avalanche.</p>';
  }

  // ── Research Avalanche ────────────────────────────────────────────────────
  renderAvalanche(company.ticker);
}

function renderBizDesc(biz) {
  if (!biz) return '';
  const short = biz.length > 320 ? biz.slice(0, 320).replace(/\s+\S+$/, '') + '…' : biz;
  const id = 'ty-biz-toggle';
  if (biz.length <= 320) return `<p class="ty-biz mb-0">${biz}</p>`;
  return `<p class="ty-biz mb-1" id="ty-biz-short">${short}</p>` +
    `<p class="ty-biz mb-1" id="ty-biz-full" style="display:none">${biz}</p>` +
    `<button class="ty-link-btn" id="${id}" onclick="` +
      `var s=document.getElementById('ty-biz-short'),f=document.getElementById('ty-biz-full'),b=document.getElementById('${id}');` +
      `if(f.style.display==='none'){f.style.display='';s.style.display='none';b.textContent='Show less';}` +
      `else{s.style.display='';f.style.display='none';b.textContent='Show more…';}` +
    `">Show more…</button>`;
}

function keyValueCard(label, value, tip) {
  return '<div class="col-md-4">' +
    `<div class="ty-stat" data-tip="${tip}">` +
      `<div class="ty-stat-label">${label}</div>` +
      `<div class="ty-stat-value">${value || '—'}</div>` +
    '</div>' +
  '</div>';
}

// ── Financial table with tabs ──────────────────────────────────────────────

function renderFinancials(company) {
  const fin = company.fin || [];
  if (!fin.length) { document.getElementById('ty-fin-section').innerHTML = ''; return; }

  const yrs = fin.map(r => r.yr);

  const tabs = [
    { id: 'income',   label: 'Income Statement' },
    { id: 'balance',  label: 'Balance Sheet' },
    { id: 'cashflow', label: 'Cash Flow' },
  ];

  const incRows = [
    { label: 'Revenue',              key: 'rev',    fmt: fmtBn },
    { label: 'Net Income',           key: 'ni',     fmt: fmtBn },
    { label: 'EPS (diluted)',        key: 'eps',    fmt: v => v != null ? '$' + v.toFixed(2) : '—' },
    { label: 'EBITDA',               key: 'ebitda', fmt: fmtBn },
  ];
  const balRows = [
    { label: 'Total Assets',         key: 'assets',     fmt: fmtBn },
    { label: 'Cash & Equivalents',   key: 'cash',       fmt: fmtBn },
    { label: 'Total Debt',           key: 'total_debt', fmt: fmtBn },
    { label: 'Stockholders Equity',  key: 'equity',     fmt: fmtBn },
    { label: 'Goodwill',             key: 'goodwill',   fmt: fmtBn },
    { label: 'Goodwill % of Assets', key: 'gw_pct',    fmt: v => v != null ? v.toFixed(1) + '%' : '—' },
  ];
  const cfRows = [
    { label: 'Operating Cash Flow',  key: 'op_cf', fmt: fmtBn },
  ];

  document.getElementById('ty-fin-section').innerHTML =
    '<div class="ty-card mb-4">' +
      '<div class="ty-card-head">' +
        '<h3 class="ty-card-title">Financial Statements</h3>' +
        '<span class="small" style="opacity:.78">USD · annual (3yr)</span>' +
      '</div>' +
      '<div class="ty-card-body" style="padding-bottom:0">' +
        '<div class="ty-tabs mb-3" id="ty-fin-tabs">' +
          tabs.map((t, i) => `<button class="ty-tab${i===0?' active':''}" data-tab="${t.id}">${t.label}</button>`).join('') +
        '</div>' +
        tabs.map((t, i) => {
          const rows = t.id === 'income' ? incRows : t.id === 'balance' ? balRows : cfRows;
          return `<div id="ty-tab-${t.id}"${i > 0 ? ' style="display:none"' : ''}>` +
            buildFinTable(fin, yrs, rows) +
          '</div>';
        }).join('') +
      '</div>' +
    '</div>';

  document.getElementById('ty-fin-tabs').addEventListener('click', e => {
    const btn = e.target.closest('.ty-tab');
    if (!btn) return;
    document.querySelectorAll('.ty-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    tabs.forEach(t => {
      document.getElementById('ty-tab-' + t.id).style.display = btn.dataset.tab === t.id ? '' : 'none';
    });
  });
}

function buildFinTable(fin, yrs, rows) {
  return '<div class="table-responsive"><table class="table ty-table mb-0">' +
    '<thead><tr><th>Metric</th>' + yrs.map(y => `<th class="text-end">${y}</th>`).join('') + '</tr></thead>' +
    '<tbody>' +
    rows.map(r => {
      const cells = fin.map(f => f[r.key]);
      return '<tr><td class="fw-semibold">' + r.label + '</td>' +
        cells.map((v, i) => {
          const prev = cells[i + 1];
          let delta = '';
          if (prev != null && prev !== 0 && v != null) {
            const d = (v - prev) / Math.abs(prev) * 100;
            delta = `<span class="delta ${d < 0 ? 'neg' : ''}">${fmtPct(d)}</span>`;
          }
          return `<td class="text-end">${r.fmt(v)} ${delta}</td>`;
        }).join('') + '</tr>';
    }).join('') +
    '</tbody></table></div>';
}

function updateRangePerf(company) {
  const s = company.series || [];
  if (!s.length) { document.getElementById('ty-range-perf').textContent = ''; return; }
  const last = s[s.length - 1].p;
  const map  = { '1y': 252, '2y': 504, '3y': 756, '5y': 1260, '10y': 2520 };
  const n    = Math.min(map[state.range] || 252, s.length);
  const start = s[s.length - n].p;
  document.getElementById('ty-range-perf').textContent =
    fmtPct((last - start) / start * 100) + ' over ' + state.range.toUpperCase();
}

// ============================================================
// RESEARCH AVALANCHE
// ============================================================

function renderAvalanche(ticker) {
  const el = document.getElementById('ty-avalanche-checks');
  el.innerHTML = TY_SITES.map(site =>
    `<label class="ty-check ${state.checks[site.id] ? 'on' : ''}" data-site="${site.id}">` +
      '<input type="checkbox"' + (state.checks[site.id] ? ' checked' : '') + '>' +
      '<span class="ty-tick"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg></span>' +
      site.label +
    '</label>'
  ).join('');
  el.querySelectorAll('.ty-check').forEach(label => {
    label.addEventListener('click', e => {
      e.preventDefault();
      const id = label.dataset.site;
      state.checks[id] = !state.checks[id];
      label.classList.toggle('on', state.checks[id]);
      label.querySelector('input').checked = state.checks[id];
    });
  });
  document.getElementById('ty-avalanche-btn').onclick = () => {
    TY_SITES.forEach(s => { if (state.checks[s.id]) window.open(s.url(ticker), '_blank'); });
  };
}

// ============================================================
// LOAD TICKER
// ============================================================

async function loadTicker(raw) {
  const t = (raw || '').toUpperCase().trim();
  if (!t) return;

  document.getElementById('tickersymbol').value = t;
  document.getElementById('ty-empty').style.display    = 'none';
  document.getElementById('ty-content').style.display  = 'none';
  document.getElementById('ty-error').style.display    = 'none';
  document.getElementById('ty-loading').style.display  = '';

  try {
    const company = await fetchTicker(t);
    state.company = company;
    state.range   = '1y';
    addRecent(t);
    renderRecent();

    document.querySelectorAll('#ty-range-btns .btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.range === '1y');
    });

    document.getElementById('ty-loading').style.display = 'none';
    document.getElementById('ty-content').style.display = '';
    renderDashboard(company);
    document.getElementById('ty-content').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    document.getElementById('ty-loading').style.display  = 'none';
    document.getElementById('ty-error').style.display    = '';
    document.getElementById('ty-empty').style.display    = 'none';
    document.getElementById('ty-error-msg').textContent =
      e.message.includes('No data') ? `No data found for "${t}". Check the ticker symbol.` : e.message;
  }
}

// ============================================================
// INIT
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  renderRecent();

  document.getElementById('ty-form').addEventListener('submit', e => {
    e.preventDefault();
    loadTicker(document.getElementById('tickersymbol').value);
  });

  document.getElementById('ty-range-btns').addEventListener('click', e => {
    const btn = e.target.closest('[data-range]');
    if (!btn || !state.company) return;
    state.range = btn.dataset.range;
    document.querySelectorAll('#ty-range-btns .btn').forEach(b => b.classList.toggle('active', b === btn));
    renderChart(document.getElementById('ty-chart-wrap'), state.company.series || [], state.range);
    updateRangePerf(state.company);
  });
});
