#!/usr/bin/env bash
# Apply staging migration. Run from repo root.
set -euo pipefail
cd terraform
terraform init -upgrade
terraform apply -var-file=staging.tfvars -auto-approve
