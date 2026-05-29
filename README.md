# TickerYeti

A fast stock research dashboard. Type a ticker, hit Yeti, and get price history, financial statements, key metrics, peers, and direct links to your favorite research sources — all in one place.

**Live site:** https://tickeryeti.com | **QA:** https://qa.tickeryeti.com

---

## What it does

Enter any US stock ticker symbol (e.g. `AAPL`, `NVDA`, `TSLA`) and hit **Yeti**. TickerYeti fetches data from Yahoo Finance and Financial Modeling Prep via a Lambda backend and renders a full research dashboard:

- **Price chart** — interactive daily close price with volume bars, hover tooltip, and selectable time ranges (1Y / 2Y / 3Y / 5Y / 10Y)
- **Key stock data** — market cap, smoothed market cap, average daily trading volume, days to cover, shares held short, total shares outstanding
- **Financial statements** — 3 years of annual data in two tabbed views:
  - *Risk Report Metrics*: Revenue, Net Income, EPS, Assets, Cash, Operating Cash Flow, Total Debt, Debt/Equity, Goodwill %
  - *Additional Metrics*: EBITDA, Goodwill, Stockholders Equity, Interest Expense
  - Year-over-year change badges on every column
  - **Copy Data button** copies the table as tab-separated values for pasting into spreadsheets or research forms; Credit Rating is included as a blank row to preserve column alignment
- **Key values** — Current Ratio, Debt/Equity, Interest Coverage
- **Valuation ratios** — P/E, P/B, P/S
- **Annual Update** — narrative summary of the company's most recent annual reporting period
- **Peers & Competitors** — clickable ticker chips to jump between related companies; hover any chip to see the full company name in a tooltip
- **Research Avalanche** — opens Yahoo Finance, Seeking Alpha, SEC EDGAR, and Finviz in new tabs simultaneously, all pre-loaded with the current ticker

All metric cards and table row labels include hover tooltips with plain-English definitions.

---

## Tech stack

- Static HTML/CSS/JS — no build step, no framework
- [Bootstrap 5](https://getbootstrap.com/)
- AWS Lambda (Python) — data fetching via `yfinance` and Financial Modeling Prep API
- AWS API Gateway — HTTPS endpoint for the Lambda
- Hosted on AWS S3, served via CloudFront (HTTPS)
- DNS via Route 53
- GA4 for analytics
- GitHub Actions for CI/CD (push to `qa` branch deploys to QA; push to `main` deploys to prod)

---

## Local development

No build tooling required. Serve the static files locally:

```bash
python3 -m http.server 8080
```

Then open http://localhost:8080. API calls hit the production Lambda by default.

---

## Deployment

Requires AWS CLI configured with appropriate credentials.

```bash
# Deploy to QA (qa.tickeryeti.com)
./deploy.sh qa

# Deploy to production (tickeryeti.com)
./deploy.sh prod
```

The deploy script syncs all site files to the appropriate S3 bucket and invalidates the CloudFront cache. Lambda is deployed separately via the AWS console or `aws lambda update-function-code`.

---

## AWS infrastructure

| Resource | Details |
|---|---|
| S3 bucket (prod) | `aws-website-tickeryeticom-llnte` |
| S3 bucket (QA) | `aws-website-qatickeryeticom-x4mxs` |
| CloudFront (prod) | `d3i4ev9bq8cg05.cloudfront.net` — alias `tickeryeti.com` |
| CloudFront (QA) | `docfyhrixmhtv.cloudfront.net` — alias `qa.tickeryeti.com` |
| SSL cert | ACM `arn:aws:acm:us-east-1:141242608176:certificate/82f3fdce-5e02-4e71-8f36-091c0fef2baf` |
| DNS | Route 53 hosted zone `Z1JWP3RZNSREJ9` |
| Lambda | Python 3.x, `yfinance` + FMP API, deployed to us-west-2 |

---

## Data sources

- **Yahoo Finance** (`yfinance`) — price series, key stats, short interest, shares outstanding, peers fallback
- **Financial Modeling Prep** — financial statements, IPO year, peer lists, company names/profiles

Data is not investment advice. See [Terms & Disclaimer](https://tickeryeti.com/terms.html).

---

## License

MIT
