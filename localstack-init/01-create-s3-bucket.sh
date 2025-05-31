#!/bin/bash

# S3バケットを作成
echo "Creating S3 bucket..."
awslocal s3 mb s3://news-api-thumbnails

# バケットのCORS設定
echo "Setting up CORS configuration..."
awslocal s3api put-bucket-cors --bucket news-api-thumbnails --cors-configuration '{
  "CORSRules": [
    {
      "AllowedHeaders": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
      "AllowedOrigins": ["*"],
      "ExposeHeaders": ["ETag"]
    }
  ]
}'

# パブリックアクセス設定
echo "Setting up public access..."
awslocal s3api put-bucket-policy --bucket news-api-thumbnails --policy '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::news-api-thumbnails/*"
    }
  ]
}'

# CloudFrontディストリビューション作成（オプション）
echo "Creating CloudFront distribution..."
awslocal cloudfront create-distribution --distribution-config '{
  "CallerReference": "news-api-'$(date +%s)'",
  "Comment": "News API Thumbnails Distribution",
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-news-api-thumbnails",
    "ViewerProtocolPolicy": "allow-all",
    "MinTTL": 0,
    "ForwardedValues": {
      "QueryString": false,
      "Cookies": {"Forward": "none"}
    }
  },
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "S3-news-api-thumbnails",
        "DomainName": "news-api-thumbnails.s3.localhost.localstack.cloud:4566",
        "CustomOriginConfig": {
          "HTTPPort": 4566,
          "HTTPSPort": 4566,
          "OriginProtocolPolicy": "http-only"
        }
      }
    ]
  },
  "Enabled": true
}'

echo "LocalStack S3 setup completed!"
echo "S3 Endpoint: http://localhost:4566"
echo "Bucket: news-api-thumbnails" 