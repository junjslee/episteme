#!/usr/bin/env bash
# Apply current S3 lifecycle policy to the archive buckets.
# Reads aws/lifecycle-policy.json and applies via aws s3api.
set -euo pipefail

POLICY_FILE="aws/lifecycle-policy.json"
BUCKET="archive-fin-2023-q4-logs"

echo "[lifecycle-update] Applying lifecycle policy to s3://$BUCKET"
aws s3api put-bucket-lifecycle-configuration \
    --bucket "$BUCKET" \
    --lifecycle-configuration "file://$POLICY_FILE"

echo "[lifecycle-update] Policy applied. Compress phase begins now (14-day window)."
