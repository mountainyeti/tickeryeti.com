#!/bin/bash
set -e

ENV=${1:-prod}

if [ "$ENV" = "qa" ]; then
  BUCKET="aws-website-qatickeryeticom-x4mxs"
  echo "Deploying to QA: s3://$BUCKET"
elif [ "$ENV" = "prod" ]; then
  BUCKET="aws-website-tickeryeticom-llnte"
  echo "Deploying to PROD: s3://$BUCKET"
else
  echo "Usage: ./deploy.sh [qa|prod]"
  exit 1
fi

EXCLUDE="--exclude .git/* --exclude deploy.sh --exclude .claude/* --exclude README.md --exclude .gitignore --exclude lambda/* --exclude tests/* --exclude requirements-test.txt"

# HTML: no-cache so browsers always check for updates after a deploy
aws s3 sync . s3://$BUCKET \
  $EXCLUDE \
  --exclude "*.js" \
  --exclude "*.css" \
  --exclude "images/*" \
  --cache-control "no-cache" \
  --delete

# JS + CSS: 1-hour browser cache (CloudFront invalidation handles CDN freshness)
aws s3 sync . s3://$BUCKET \
  $EXCLUDE \
  --exclude "*.html" \
  --exclude "images/*" \
  --cache-control "public, max-age=3600" \
  --delete

# Images: 1-week browser cache (they never change)
aws s3 sync . s3://$BUCKET \
  $EXCLUDE \
  --exclude "*.html" \
  --exclude "*.js" \
  --exclude "*.css" \
  --cache-control "public, max-age=604800" \
  --delete

echo "Done."
