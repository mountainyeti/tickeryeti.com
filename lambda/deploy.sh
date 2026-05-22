#!/bin/bash
set -e

FUNCTION="tickeryeti-api"
REGION="us-west-2"
ACCOUNT="141242608176"
ROLE_NAME="tickeryeti-lambda-role"
ROLE_ARN="arn:aws:iam::${ACCOUNT}:role/${ROLE_NAME}"
FMP_KEY="${FMP_KEY:-678e882c6502dd2fe698fe5c08a31b956098b2cc2395667db92231789b76ef14}"

cd "$(dirname "$0")"

echo "==> Packaging function..."
rm -f function.zip
zip -j function.zip function.py -q
echo "    $(du -sh function.zip | cut -f1) zipped"

echo "==> Checking IAM role..."
if ! aws iam get-role --role-name "$ROLE_NAME" --region "$REGION" &>/dev/null; then
  echo "    Creating role $ROLE_NAME..."
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
    --output text > /dev/null
  aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  echo "    Waiting for role propagation..."
  sleep 12
else
  echo "    Role exists."
fi

echo "==> Checking Lambda function..."
if aws lambda get-function --function-name "$FUNCTION" --region "$REGION" &>/dev/null; then
  echo "    Updating function code..."
  aws lambda update-function-code \
    --function-name "$FUNCTION" \
    --zip-file fileb://function.zip \
    --region "$REGION" \
    --output text > /dev/null
  aws lambda wait function-updated --function-name "$FUNCTION" --region "$REGION"
  echo "    Updating environment variables..."
  aws lambda update-function-configuration \
    --function-name "$FUNCTION" \
    --environment "Variables={FMP_KEY=${FMP_KEY}}" \
    --region "$REGION" \
    --output text > /dev/null
else
  echo "    Creating Lambda function..."
  aws lambda create-function \
    --function-name "$FUNCTION" \
    --runtime python3.12 \
    --handler function.lambda_handler \
    --role "$ROLE_ARN" \
    --zip-file fileb://function.zip \
    --timeout 30 \
    --memory-size 256 \
    --environment "Variables={FMP_KEY=${FMP_KEY}}" \
    --region "$REGION" \
    --output text > /dev/null
  aws lambda wait function-active --function-name "$FUNCTION" --region "$REGION"

  echo "    Adding public invoke permission..."
  aws lambda add-permission \
    --function-name "$FUNCTION" \
    --statement-id AllowPublicURL \
    --action lambda:InvokeFunctionUrl \
    --principal "*" \
    --function-url-auth-type NONE \
    --region "$REGION" \
    --output text > /dev/null

  echo "    Creating Function URL..."
  aws lambda create-function-url-config \
    --function-name "$FUNCTION" \
    --auth-type NONE \
    --cors '{"AllowOrigins":["*"],"AllowMethods":["GET"],"AllowHeaders":["Content-Type"],"MaxAge":86400}' \
    --region "$REGION" \
    --output text > /dev/null
fi

echo ""
echo "==> Function URL:"
URL=$(aws lambda get-function-url-config \
  --function-name "$FUNCTION" \
  --region "$REGION" \
  --query 'FunctionUrl' \
  --output text)
echo "    $URL"
echo ""
echo "==> Test: curl \"${URL}?ticker=AAPL\""
