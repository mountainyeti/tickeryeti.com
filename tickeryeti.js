// ============================================================
// DATA LAYER — swap fetchTicker() for real API calls later
// ============================================================

const TY_SITES = [
  { id: 'yahoo',    label: 'Yahoo Finance',       url: t => `https://finance.yahoo.com/quote/${t}` },
  { id: 'seeking',  label: 'Seeking Alpha',       url: t => `https://seekingalpha.com/symbol/${t}/earnings` },
  { id: 'edgar',    label: 'SEC EDGAR',           url: t => `https://www.sec.gov/cgi-bin/browse-edgar?CIK=${t}&owner=exclude&action=getcompany` },
  { id: 'finviz',   label: 'Finviz',              url: t => `https://finviz.com/quote.ashx?t=${t}` },
  { id: 'stanford', label: 'Stanford Securities', url: _  => 'https://securities.stanford.edu/filings.html' },
];

// Seeded RNG for deterministic chart shapes
function tySeed(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = (h * 16777619) >>> 0; }
  return () => {
    h = (h + 0x6D2B79F5) >>> 0;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function tyNormal(rnd) {
  let u = 0, v = 0;
  while (!u) u = rnd();
  while (!v) v = rnd();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}
function tyMakeSeries(ticker, startPrice, endPrice, vol, yrs) {
  vol = vol || 0.018; yrs = yrs || 5;
  const rnd = tySeed(ticker + '|v2|' + yrs);
  const N = yrs * 252;
  const today = new Date(2026, 4, 20);
  const y = [];
  let acc = 0;
  for (let i = 0; i < N; i++) { acc += tyNormal(rnd) * vol; y.push(acc); }
  const b = (Math.log(endPrice / startPrice) - (y[N-1] - y[0])) / (N - 1);
  return y.map((yi, i) => {
    const d = new Date(today);
    d.setDate(d.getDate() - (N - 1 - i));
    return { d, p: startPrice * Math.exp((yi - y[0]) + b * i) };
  });
}

const TY_COMPANIES = {
  AAPL: {
    ticker: 'AAPL', name: 'Apple Inc.', sector: 'Technology',
    industry: 'Consumer Electronics', exchange: 'NASDAQ',
    biz: 'Designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories worldwide, alongside a growing services business spanning the App Store, advertising, payments, and subscriptions.',
    stats: { mcap: '$3.18T', pe: '29.4', pb: '47.8', rev: '$391.0B', eps: '$6.43', ni: '$96.9B' },
    fin: [
      { yr: 'FY24', rev: 391.0, ni: 96.9, eps: 6.43 },
      { yr: 'FY23', rev: 383.3, ni: 97.0, eps: 6.16 },
      { yr: 'FY22', rev: 394.3, ni: 99.8, eps: 6.11 },
    ],
    peers: [
      { t: 'MSFT', n: 'Microsoft', chg: +0.42 },
      { t: 'GOOGL', n: 'Alphabet', chg: -0.18 },
      { t: 'AMZN', n: 'Amazon', chg: +1.06 },
      { t: 'META', n: 'Meta', chg: +0.81 },
      { t: 'SONY', n: 'Sony Group', chg: -0.34 },
    ],
    series: tyMakeSeries('AAPL', 125, 210, 0.016),
  },
  NVDA: {
    ticker: 'NVDA', name: 'NVIDIA Corporation', sector: 'Technology',
    industry: 'Semiconductors', exchange: 'NASDAQ',
    biz: 'Designs accelerated computing platforms and GPUs powering AI training and inference, data centers, gaming, professional visualization, and automotive — with a dominant share of the discrete GPU market.',
    stats: { mcap: '$3.42T', pe: '62.1', pb: '54.9', rev: '$130.5B', eps: '$2.95', ni: '$72.9B' },
    fin: [
      { yr: 'FY25', rev: 130.5, ni: 72.9, eps: 2.95 },
      { yr: 'FY24', rev: 60.9,  ni: 29.8, eps: 1.21 },
      { yr: 'FY23', rev: 26.9,  ni: 4.4,  eps: 0.18 },
    ],
    peers: [
      { t: 'AMD',  n: 'Advanced Micro Devices', chg: +1.92 },
      { t: 'INTC', n: 'Intel', chg: -0.71 },
      { t: 'AVGO', n: 'Broadcom', chg: +0.55 },
      { t: 'TSM',  n: 'Taiwan Semi', chg: +0.31 },
      { t: 'ARM',  n: 'Arm Holdings', chg: +0.74 },
    ],
    series: tyMakeSeries('NVDA', 8, 140, 0.028),
  },
  MSFT: {
    ticker: 'MSFT', name: 'Microsoft Corporation', sector: 'Technology',
    industry: 'Software — Infrastructure', exchange: 'NASDAQ',
    biz: 'Develops, licenses, and supports software, services, devices, and solutions — including Azure cloud, Microsoft 365, Windows, LinkedIn, Dynamics, and a fast-growing AI platform stack.',
    stats: { mcap: '$3.11T', pe: '36.7', pb: '11.5', rev: '$245.1B', eps: '$11.80', ni: '$88.1B' },
    fin: [
      { yr: 'FY24', rev: 245.1, ni: 88.1, eps: 11.80 },
      { yr: 'FY23', rev: 211.9, ni: 72.4, eps: 9.68  },
      { yr: 'FY22', rev: 198.3, ni: 72.7, eps: 9.65  },
    ],
    peers: [
      { t: 'AAPL',  n: 'Apple', chg: +0.21 },
      { t: 'GOOGL', n: 'Alphabet', chg: -0.18 },
      { t: 'AMZN',  n: 'Amazon', chg: +1.06 },
      { t: 'ORCL',  n: 'Oracle', chg: +0.44 },
      { t: 'CRM',   n: 'Salesforce', chg: -0.10 },
    ],
    series: tyMakeSeries('MSFT', 185, 430, 0.015),
  },
  TSLA: {
    ticker: 'TSLA', name: 'Tesla, Inc.', sector: 'Consumer Cyclical',
    industry: 'Auto Manufacturers', exchange: 'NASDAQ',
    biz: 'Designs, develops, manufactures, and sells electric vehicles and stationary energy storage, with growing exposure to autonomy software, charging infrastructure, and robotics.',
    stats: { mcap: '$812B', pe: '71.3', pb: '11.2', rev: '$97.7B', eps: '$2.27', ni: '$7.1B' },
    fin: [
      { yr: 'FY24', rev: 97.7, ni: 7.1,  eps: 2.27 },
      { yr: 'FY23', rev: 96.8, ni: 15.0, eps: 4.30 },
      { yr: 'FY22', rev: 81.5, ni: 12.6, eps: 3.62 },
    ],
    peers: [
      { t: 'F',     n: 'Ford Motor', chg: -0.22 },
      { t: 'GM',    n: 'General Motors', chg: +0.14 },
      { t: 'RIVN',  n: 'Rivian', chg: -1.42 },
      { t: 'TM',    n: 'Toyota', chg: +0.05 },
      { t: 'BYDDY', n: 'BYD', chg: +0.62 },
    ],
    series: tyMakeSeries('TSLA', 45, 245, 0.033),
  },
};

function tyResolveTicker(raw) {
  const t = (raw || '').toUpperCase().trim();
  if (!t) return null;
  if (TY_COMPANIES[t]) return TY_COMPANIES[t];
  return {
    ticker: t, name: t + ' Holdings', sector: '—', industry: '—', exchange: '—', isStub: true,
    biz: 'No data on file for this ticker. Use Research Avalanche below to open it on Yahoo Finance, Seeking Alpha, or SEC EDGAR.',
    stats: { mcap: '—', pe: '—', pb: '—', rev: '—', eps: '—', ni: '—' },
    fin: [
      { yr: 'FY24', rev: 0, ni: 0, eps: 0 },
      { yr: 'FY23', rev: 0, ni: 0, eps: 0 },
      { yr: 'FY22', rev: 0, ni: 0, eps: 0 },
    ],
    peers: [],
    series: tyMakeSeries(t, 50, 75, 0.022),
  };
}

// Stub for future API integration
async function fetchTicker(ticker) {
  return tyResolveTicker(ticker);
}

// Formatters
function tyFmtPrice(p) {
  return '$' + p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function tyFmtBn(v) {
  return v >= 1 ? '$' + v.toFixed(1) + 'B' : '$' + (v * 1000).toFixed(0) + 'M';
}
function tyFmtDate(d) {
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}
function tyFmtPct(p) {
  return (p >= 0 ? '+' : '') + p.toFixed(2) + '%';
}

// ============================================================
// APP STATE
// ============================================================

const state = {
  company: null,
  range: '1y',
  checks: { yahoo: true, seeking: true, edgar: true, finviz: true, stanford: false },
};

// ============================================================
// RECENT TICKERS
// ============================================================

function getRecent() {
  try {
    const s = JSON.parse(localStorage.getItem('ty_recent') || '[]');
    return s.length ? s : ['AAPL', 'NVDA', 'MSFT', 'TSLA'];
  } catch {
    return ['AAPL', 'NVDA', 'MSFT', 'TSLA'];
  }
}

function addRecent(t) {
  try {
    const r = JSON.parse(localStorage.getItem('ty_recent') || '[]');
    localStorage.setItem('ty_recent', JSON.stringify(
      [t, ...r.filter(x => x !== t)].slice(0, 6)
    ));
  } catch {}
}

function renderRecent() {
  const row = document.getElementById('ty-recent-row');
  const tickers = getRecent();
  row.innerHTML =
    '<span style="font-size:11px;text-transform:uppercase;letter-spacing:0.14em;opacity:0.8">Recent</span>' +
    tickers.map(t =>
      `<button type="button" class="ty-peer" style="padding:5px 12px" data-ticker="${t}">` +
      `<span class="ty-peer-tick">${t}</span></button>`
    ).join('');
  row.querySelectorAll('[data-ticker]').forEach(btn => {
    btn.addEventListener('click', () => loadTicker(btn.dataset.ticker));
  });
}

// ============================================================
// CHART
// ============================================================

function getChartSlice(series, range) {
  const map = { '1y': 252, '2y': 504, '3y': 756, '5y': 1260 };
  return series.slice(-Math.min(map[range] || 252, series.length));
}

function renderChart(wrap, series, range) {
  const data = getChartSlice(series, range);
  const W = 1100, H = 320, PADL = 60, PADR = 18, PADT = 16, PADB = 32;
  const iw = W - PADL - PADR, ih = H - PADT - PADB;

  let minP = Infinity, maxP = -Infinity;
  data.forEach(d => { if (d.p < minP) minP = d.p; if (d.p > maxP) maxP = d.p; });
  const pad = (maxP - minP) * 0.08 || 1;
  minP -= pad; maxP += pad;

  const xv = i => PADL + (i / ((data.length - 1) || 1)) * iw;
  const yv = p => PADT + (1 - (p - minP) / ((maxP - minP) || 1)) * ih;

  const pts = data.map((d, i) =>
    (i === 0 ? 'M' : 'L') + xv(i).toFixed(1) + ',' + yv(d.p).toFixed(1)
  ).join(' ');
  const area = pts +
    ' L' + xv(data.length - 1).toFixed(1) + ',' + (PADT + ih).toFixed(1) +
    ' L' + xv(0).toFixed(1) + ',' + (PADT + ih).toFixed(1) + ' Z';

  const yTicks = Array.from({ length: 6 }, (_, i) => minP + (maxP - minP) * i / 5);

  const seen = new Set();
  const xTicks = [];
  data.forEach((d, i) => {
    const m = d.d.getMonth(), yr = d.d.getFullYear(), key = yr + '-' + m;
    if (!seen.has(key) && (m === 0 || m === 6) && data.length > 60) {
      seen.add(key);
      const label = m === 0
        ? String(yr)
        : d.d.toLocaleString(undefined, { month: 'short' }) + ' ' + String(yr).slice(-2);
      xTicks.push({ i, label });
    }
  });

  wrap.innerHTML =
    '<svg class="ty-chart-svg" id="ty-svg" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none">' +
      '<defs>' +
        '<linearGradient id="ty-fill" x1="0" y1="0" x2="0" y2="1">' +
          '<stop offset="0%" stop-color="#fff" stop-opacity="0.34"/>' +
          '<stop offset="100%" stop-color="#fff" stop-opacity="0"/>' +
        '</linearGradient>' +
      '</defs>' +
      yTicks.map(v =>
        '<line x1="' + PADL + '" x2="' + (W - PADR) + '" y1="' + yv(v).toFixed(1) + '" y2="' + yv(v).toFixed(1) + '" stroke="rgba(255,255,255,0.18)" stroke-width="1"/>' +
        '<text x="' + (PADL - 8) + '" y="' + (yv(v) + 4).toFixed(1) + '" text-anchor="end" font-size="11" fill="rgba(255,255,255,0.78)" font-family="Helvetica Neue,Helvetica,Arial,sans-serif">$' + v.toFixed(v < 10 ? 2 : 0) + '</text>'
      ).join('') +
      xTicks.slice(0, 9).map(t =>
        '<text x="' + xv(t.i).toFixed(1) + '" y="' + (H - 8) + '" text-anchor="middle" font-size="11" fill="rgba(255,255,255,0.78)" font-family="Helvetica Neue,Helvetica,Arial,sans-serif">' + t.label + '</text>'
      ).join('') +
      '<path d="' + area + '" fill="url(#ty-fill)"/>' +
      '<path d="' + pts + '" fill="none" stroke="#fff" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>' +
      '<line id="ty-vline" stroke="rgba(255,255,255,0.55)" stroke-dasharray="3 3" style="display:none"/>' +
      '<circle id="ty-dot" r="5" fill="var(--ty-blue)" stroke="#fff" stroke-width="2" style="display:none"/>' +
    '</svg>' +
    '<div id="ty-tip" class="ty-chart-hover" style="display:none">' +
      '<div class="hv-date" id="ty-tip-date"></div>' +
      '<div class="hv-price" id="ty-tip-price"></div>' +
    '</div>';

  const svg = wrap.querySelector('#ty-svg');
  const vline = wrap.querySelector('#ty-vline');
  const dot = wrap.querySelector('#ty-dot');
  const tip = wrap.querySelector('#ty-tip');
  const tipDate = wrap.querySelector('#ty-tip-date');
  const tipPrice = wrap.querySelector('#ty-tip-price');

  svg.addEventListener('mousemove', e => {
    const rect = svg.getBoundingClientRect();
    const xPos = ((e.clientX - rect.left) / rect.width) * W;
    const idx = Math.max(0, Math.min(data.length - 1,
      Math.round(((xPos - PADL) / iw) * (data.length - 1))
    ));
    const cx = xv(idx), cy = yv(data[idx].p);

    vline.setAttribute('x1', cx); vline.setAttribute('x2', cx);
    vline.setAttribute('y1', PADT); vline.setAttribute('y2', PADT + ih);
    vline.style.display = '';
    dot.setAttribute('cx', cx); dot.setAttribute('cy', cy);
    dot.style.display = '';

    tip.style.display = '';
    tip.style.left = (cx / W * 100) + '%';
    tip.style.top = (cy / H * 100) + '%';
    tipDate.textContent = tyFmtDate(data[idx].d);
    tipPrice.textContent = tyFmtPrice(data[idx].p);
  });

  svg.addEventListener('mouseleave', () => {
    vline.style.display = 'none';
    dot.style.display = 'none';
    tip.style.display = 'none';
  });
}

// ============================================================
// DASHBOARD
// ============================================================

function renderDashboard(company) {
  const s = company.series;
  const last = s[s.length - 1].p;
  const yrAgo = (s[s.length - 253] || s[0]).p;
  const pct = (last - yrAgo) / yrAgo * 100;
  const chgUp = pct >= 0;
  const initials = company.name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase();

  // Company header
  document.getElementById('ty-co-col').innerHTML =
    '<div class="d-flex gap-3 align-items-start">' +
      '<div class="ty-co-logo">' + initials + '</div>' +
      '<div>' +
        '<h2 class="fw-bold mb-1" style="letter-spacing:-0.01em;font-size:26px">' +
          company.name +
          '<span class="ty-ticker-badge">' + company.ticker + '</span>' +
        '</h2>' +
        '<div class="d-flex flex-wrap gap-2 mb-2">' +
          '<span class="ty-sector-tag"><span class="ty-dot"></span>' + company.sector + '</span>' +
          '<span class="ty-sector-tag">' + company.industry + '</span>' +
          '<span class="ty-sector-tag">' + company.exchange + '</span>' +
        '</div>' +
        '<p class="ty-biz mb-0">' + company.biz + '</p>' +
      '</div>' +
    '</div>';

  document.getElementById('ty-price-col').innerHTML =
    '<div class="ty-price-now">' + tyFmtPrice(last) + '</div>' +
    '<div class="ty-price-chg ' + (chgUp ? 'up' : 'down') + '">' +
      '<span class="arrow">' + (chgUp ? '▲' : '▼') + '</span>' +
      tyFmtPrice(Math.abs(last - yrAgo)) + ' (' + tyFmtPct(pct) + ') · 1Y' +
    '</div>' +
    '<div class="small mt-1" style="opacity:0.78">As of May 20, 2026 · close</div>';

  // Chart
  document.getElementById('ty-chart-label').textContent = 'Price · ' + company.ticker;
  renderChart(document.getElementById('ty-chart-wrap'), company.series, state.range);
  updateRangePerf(company);

  // Stats
  const stats = [
    { label: 'Market Cap',    value: company.stats.mcap, sub: company.exchange },
    { label: 'P/E (TTM)',     value: company.stats.pe,   sub: 'trailing 12 mo' },
    { label: 'Revenue',       value: company.stats.rev,  sub: 'last fiscal yr' },
    { label: 'Net Income',    value: company.stats.ni,   sub: company.fin[0].yr },
    { label: 'EPS (diluted)', value: company.stats.eps,  sub: 'TTM' },
    { label: 'P/B',           value: company.stats.pb,   sub: 'book value' },
  ];
  document.getElementById('ty-stats-row').innerHTML = stats.map(s =>
    '<div class="col-6 col-md-4 col-xl-2">' +
      '<div class="ty-stat">' +
        '<div class="ty-stat-label">' + s.label + '</div>' +
        '<div class="ty-stat-value">' + s.value + '</div>' +
        '<div class="ty-stat-sub">' + s.sub + '</div>' +
      '</div>' +
    '</div>'
  ).join('');

  // Financials table
  document.getElementById('ty-fin-table').innerHTML =
    '<thead><tr>' +
      '<th>Metric</th>' +
      company.fin.map(r => '<th class="text-end">' + r.yr + '</th>').join('') +
    '</tr></thead>' +
    '<tbody>' +
      finRow('Revenue',    company.fin.map(r => r.rev), tyFmtBn) +
      finRow('Net income', company.fin.map(r => r.ni),  tyFmtBn) +
      finRow('EPS',        company.fin.map(r => r.eps), v => '$' + v.toFixed(2)) +
    '</tbody>';

  // Peers
  document.getElementById('ty-peers-count').textContent = company.peers.length + ' tickers';
  const peersBody = document.getElementById('ty-peers-body');
  if (company.peers.length) {
    peersBody.innerHTML =
      '<div class="d-flex flex-wrap gap-2">' +
      company.peers.map(p =>
        '<button class="ty-peer" data-ticker="' + p.t + '">' +
          '<span class="ty-peer-tick">' + p.t + '</span>' +
          '<span class="ty-peer-name">' + p.n + '</span>' +
          '<span class="ty-peer-chg">' + tyFmtPct(p.chg) + '</span>' +
        '</button>'
      ).join('') +
      '</div>';
    peersBody.querySelectorAll('[data-ticker]').forEach(btn => {
      btn.addEventListener('click', () => loadTicker(btn.dataset.ticker));
    });
  } else {
    peersBody.innerHTML = '<p class="small mb-0" style="opacity:0.78">No peers on file. Try Research Avalanche below.</p>';
  }

  // Research Avalanche
  renderAvalanche(company.ticker);
}

function finRow(label, cells, fmt) {
  return '<tr>' +
    '<td class="fw-semibold">' + label + '</td>' +
    cells.map((v, i) => {
      const prev = cells[i + 1];
      let delta = '';
      if (prev !== undefined && prev !== 0) {
        const d = (v - prev) / Math.abs(prev) * 100;
        delta = '<span class="delta ' + (d < 0 ? 'neg' : '') + '">' + tyFmtPct(d) + '</span>';
      }
      return '<td class="text-end">' + fmt(v) + ' ' + delta + '</td>';
    }).join('') +
    '</tr>';
}

function updateRangePerf(company) {
  const s = company.series;
  const last = s[s.length - 1].p;
  const map = { '1y': 252, '2y': 504, '3y': 756, '5y': 1260 };
  const n = Math.min(map[state.range] || 252, s.length);
  const start = s[s.length - n].p;
  document.getElementById('ty-range-perf').textContent =
    tyFmtPct((last - start) / start * 100) + ' over ' + state.range.toUpperCase();
}

// ============================================================
// RESEARCH AVALANCHE
// ============================================================

function renderAvalanche(ticker) {
  const checksEl = document.getElementById('ty-avalanche-checks');
  checksEl.innerHTML = TY_SITES.map(site =>
    '<label class="ty-check ' + (state.checks[site.id] ? 'on' : '') + '" data-site="' + site.id + '">' +
      '<input type="checkbox"' + (state.checks[site.id] ? ' checked' : '') + '>' +
      '<span class="ty-tick">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">' +
          '<path d="M5 13l4 4L19 7"/>' +
        '</svg>' +
      '</span>' +
      site.label +
    '</label>'
  ).join('');

  checksEl.querySelectorAll('.ty-check').forEach(label => {
    label.addEventListener('click', e => {
      e.preventDefault();
      const id = label.dataset.site;
      state.checks[id] = !state.checks[id];
      label.classList.toggle('on', state.checks[id]);
      label.querySelector('input').checked = state.checks[id];
    });
  });

  document.getElementById('ty-avalanche-btn').onclick = () => {
    TY_SITES.forEach(site => {
      if (state.checks[site.id]) window.open(site.url(ticker), '_blank');
    });
  };
}

// ============================================================
// LOAD TICKER
// ============================================================

async function loadTicker(raw) {
  const t = (raw || '').toUpperCase().trim();
  if (!t) return;

  const company = await fetchTicker(t);
  state.company = company;
  state.range = '1y';

  addRecent(t);
  renderRecent();
  document.getElementById('tickersymbol').value = t;

  document.getElementById('ty-empty').style.display = 'none';
  document.getElementById('ty-content').style.display = '';

  document.querySelectorAll('#ty-range-btns .btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.range === '1y');
  });

  renderDashboard(company);

  setTimeout(() => {
    const top = document.getElementById('ty-dash').getBoundingClientRect().top + window.scrollY - 16;
    window.scrollTo({ top, behavior: 'smooth' });
  }, 50);
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
    document.querySelectorAll('#ty-range-btns .btn').forEach(b => {
      b.classList.toggle('active', b === btn);
    });
    renderChart(document.getElementById('ty-chart-wrap'), state.company.series, state.range);
    updateRangePerf(state.company);
  });
});
