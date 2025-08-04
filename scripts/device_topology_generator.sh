#!/bin/bash
set -a
source .env
set +a

echo "$QDASH_API_URL"

API_URL=${QDASH_API_URL:-http://localhost:6004/api}

echo "Using QDash API base URL: ${API_URL}"

echo "Posting device topology data..."
curl -X POST "${API_URL}/device_topology" \
  -H 'accept: application/json' \
  -H 'X-Username: admin' \
  -H 'Content-Type: application/json' \
  -d @config/device_topology_request.json | jq . > config/device_topology.json

echo "Generating device topology plot..."
curl -X POST "${API_URL}/device_topology/plot" \
  -H 'accept: */*' \
  -H 'X-Username: admin' \
  -H 'Content-Type: application/json' \
  -d @config/device_topology.json > config/device_topology.png

echo "Process complete. 'device_topology.png' has been created."
