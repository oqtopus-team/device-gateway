 #!/bin/bash
set -euo pipefail

set -a
source .env
set +a

API_URL=${QDASH_API_URL:-http://localhost:6004}
TOKEN=${QDASH_API_TOKEN:-}

ZIP_PATH="./tmp/qubex-config.zip"

cleanup() {
  rm -f "$ZIP_PATH"
}
trap cleanup EXIT

echo "Using QDash API base URL: ${API_URL}"

mkdir -p qubex-config tmp

echo "Downloading calibration note..."
curl --fail -sS -X GET "${API_URL}/calibrations/note" \
  -H 'accept: application/json' \
  -H "Authorization: Bearer ${TOKEN}" \
  | jq '.note' > qubex-config/calib_note.json

echo "Downloading Qubex configuration..."
curl --fail -sS -L -X GET \
  "${API_URL}/files/zip?path=%2Fapp%2Fconfig%2Fqubex-config" \
  -H "Authorization: Bearer ${TOKEN}" \
  -o "$ZIP_PATH"

rm -rf ./qubex-config
mkdir -p ./qubex-config

  unzip -oq "$ZIP_PATH" -d ./qubex-config

  echo "Qubex configuration downloaded."