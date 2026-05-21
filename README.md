# TickerYeti

A simple web tool that opens all the research tabs you need for a given stock ticker symbol in one click — Yahoo Finance, Seeking Alpha, SEC EDGAR, Finviz, and Stanford Securities Class Action Search.

**Live site:** https://tickeryeti.com

---

## What it does

Enter a stock ticker (e.g. `AAPL`) and hit **Yeti**. TickerYeti opens a new tab for each of the selected research sources, pre-loaded for that ticker. Uncheck any sources you don't want.

## Tech stack

- Static HTML/CSS/JS — no build step, no framework
- [Bootstrap 5](https://getbootstrap.com/)
- Hosted on AWS S3, served via CloudFront (HTTPS)
- DNS via Route 53

## Local development

No build tooling required. Just open `index.html` in a browser, or run a local server:

```bash
npx serve .
```

Then open http://localhost:3000.

## Deployment

Requires AWS CLI configured with appropriate credentials.

```bash
# Deploy to QA (qa.tickeryeti.com)
./deploy.sh qa

# Deploy to production (tickeryeti.com)
./deploy.sh prod
```

The deploy script syncs all site files to the appropriate S3 bucket. CloudFront serves the content — cache invalidation may be needed for changes to take effect immediately (CloudFront default TTL is 24 hours).

## AWS infrastructure

| Resource | Details |
|---|---|
| S3 bucket (prod) | `aws-website-tickeryeticom-llnte` |
| S3 bucket (QA) | `aws-website-qatickeryeticom-x4mxs` |
| CloudFront (prod) | `d3i4ev9bq8cg05.cloudfront.net` — alias `tickeryeti.com` |
| CloudFront (QA) | `docfyhrixmhtv.cloudfront.net` — alias `qa.tickeryeti.com` |
| SSL cert | ACM `arn:aws:acm:us-east-1:141242608176:certificate/82f3fdce-5e02-4e71-8f36-091c0fef2baf` |
| DNS | Route 53 hosted zone `Z1JWP3RZNSREJ9` |

## License

MIT
