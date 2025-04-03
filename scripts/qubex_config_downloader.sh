#!/bin/bash
set -e

API_URL=${QDASH_API_URL:-http://localhost:5715/api}

echo "Using QDash API base URL: ${API_URL}"

echo "Downloading calibration note..."
curl -X GET "${API_URL}/calibration/note" \
  -H 'accept: application/json' \
  -H 'X-Username: orangekame3' | jq '.note' > qubex_config/calib_note.json

echo "Process complete. 'calib_note.json' has been created."
