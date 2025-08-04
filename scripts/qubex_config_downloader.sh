#!/bin/bash
set -a
source .env
set +a

echo "$QDASH_API_URL"

API_URL=${QDASH_API_URL:-http://localhost:6004/api}

echo "Using QDash API base URL: ${API_URL}"

echo "Downloading calibration note..."
curl -X GET "${API_URL}/calibration/note" \
  -H 'accept: application/json' \
  -H 'X-Username: admin' | jq '.note' > qubex_config/calib_note.json

echo "Process complete. 'calib_note.json' has been created."


echo "Downloading Qubex configuration..."
mkdir -p ./tmp
curl -X 'GET' \
  "${API_URL}/file/zip?path=%2Fapp%2Fconfig%2F" \
  -H 'accept: */*' \
  --output ./tmp/config.zip
unzip -o ./tmp/config.zip -d ./qubex_config/
rm -rf ./tmp/config.zip
echo "Downloading Qubex configuration..."
