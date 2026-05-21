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

aws s3 sync . s3://$BUCKET \
  --exclude ".git/*" \
  --exclude "deploy.sh" \
  --exclude ".claude/*" \
  --exclude "README.md" \
  --exclude ".gitignore" \
  --delete

echo "Done."
