import re
import subprocess
import time
import pytest
from playwright.sync_api import Page, expect

BASE_URL = 'http://localhost:8765'


@pytest.fixture(scope='session', autouse=True)
def http_server():
    proc = subprocess.Popen(
        ['python3', '-m', 'http.server', '8765', '--directory', '.'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1)
    yield
    proc.terminate()


# ── Static structure ───────────────────────────────────────────────────────────

def test_page_title(page: Page):
    page.goto(BASE_URL)
    expect(page).to_have_title('TickerYeti')

def test_search_form_visible(page: Page):
    page.goto(BASE_URL)
    expect(page.locator('#tickersymbol')).to_be_visible()
    expect(page.locator('#ty-form button.ty-btn-yeti')).to_be_visible()

def test_recent_tickers_row_visible(page: Page):
    page.goto(BASE_URL)
    expect(page.locator('#ty-recent-row')).to_be_visible()

def test_navbar_links(page: Page):
    page.goto(BASE_URL)
    expect(page.locator('a[href="help.html"]')).to_be_visible()

def test_hero_image_loads(page: Page):
    page.goto(BASE_URL)
    expect(page.locator('.ty-hero-img')).to_be_visible()

def test_empty_hint_shown_before_search(page: Page):
    page.goto(BASE_URL)
    expect(page.locator('#ty-empty')).to_be_visible()
    expect(page.locator('#ty-content')).to_be_hidden()


# ── End-to-end: search a ticker ───────────────────────────────────────────────

def test_ticker_search_loads_dashboard(page: Page):
    page.goto(BASE_URL)
    page.fill('#tickersymbol', 'AAPL')
    page.click('#ty-form button.ty-btn-yeti')
    # Loading state should appear first
    expect(page.locator('#ty-loading')).to_be_visible()
    # Then dashboard content (allow time for the API call)
    expect(page.locator('#ty-content')).to_be_visible(timeout=30_000)
    expect(page.locator('#ty-empty')).to_be_hidden()

def test_company_header_renders(page: Page):
    page.goto(BASE_URL)
    page.fill('#tickersymbol', 'AAPL')
    page.click('#ty-form button.ty-btn-yeti')
    expect(page.locator('#ty-content')).to_be_visible(timeout=30_000)
    # Company name and ticker badge
    expect(page.locator('#ty-co-col h2')).to_contain_text('Apple')
    expect(page.locator('.ty-ticker-badge')).to_contain_text('AAPL')

def test_chart_renders(page: Page):
    page.goto(BASE_URL)
    page.fill('#tickersymbol', 'AAPL')
    page.click('#ty-form button.ty-btn-yeti')
    expect(page.locator('#ty-content')).to_be_visible(timeout=30_000)
    expect(page.locator('#ty-chart-wrap svg')).to_be_visible()

def test_range_buttons_switch_chart(page: Page):
    page.goto(BASE_URL)
    page.fill('#tickersymbol', 'AAPL')
    page.click('#ty-form button.ty-btn-yeti')
    expect(page.locator('#ty-content')).to_be_visible(timeout=30_000)
    page.click('[data-range="5y"]')
    expect(page.locator('[data-range="5y"]')).to_have_class(re.compile(r'.*active.*'))

def test_financial_tabs_switch(page: Page):
    page.goto(BASE_URL)
    page.fill('#tickersymbol', 'AAPL')
    page.click('#ty-form button.ty-btn-yeti')
    expect(page.locator('#ty-content')).to_be_visible(timeout=30_000)
    page.click('.ty-tab:has-text("Additional Metrics")')
    expect(page.locator('#ty-tab-additional')).to_be_visible()
    expect(page.locator('#ty-tab-risk')).to_be_hidden()

def test_invalid_ticker_shows_error(page: Page):
    page.goto(BASE_URL)
    page.fill('#tickersymbol', 'ZZZINVALIDXYZ')
    page.click('#ty-form button.ty-btn-yeti')
    expect(page.locator('#ty-error')).to_be_visible(timeout=30_000)
    expect(page.locator('#ty-content')).to_be_hidden()
