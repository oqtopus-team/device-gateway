#!/usr/bin/env bash
set -euo pipefail

CHIP_ID=${QUBEX_CHIP_ID:-64Qv3}
QUBEX_CONFIG_DIR=${QUBEX_CONFIG_DIR:-qubex-config/${CHIP_ID}}
CALIB_NOTE_PATH=${CALIB_NOTE_PATH:-${QUBEX_CONFIG_DIR}/calibration/calib_note.json}
PARAMS_DIR=${PARAMS_DIR:-${QUBEX_CONFIG_DIR}/params}
REQUEST_JSON=${DEVICE_TOPOLOGY_REQUEST_JSON_PATH:-config/device_topology_request.json}
OUTPUT_JSON=${DEVICE_TOPOLOGY_JSON_PATH:-config/device_topology.json}
OUTPUT_PNG=${DEVICE_TOPOLOGY_PNG_PATH:-config/device_topology.png}
QDASH_REPO=${QDASH_REPO:-../qdash}
CHIP_SIZE=${QUBEX_NUM_QUBITS:-}
MPLCONFIGDIR=${MPLCONFIGDIR:-/tmp/matplotlib}
export MPLCONFIGDIR

if [[ -z "${CHIP_SIZE}" && "${CHIP_ID}" =~ ^([0-9]+)Q ]]; then
  CHIP_SIZE="${BASH_REMATCH[1]}"
fi

if [[ ! -f "${REQUEST_JSON}" && -f "config/example/device_topology_request.json" ]]; then
  REQUEST_JSON="config/example/device_topology_request.json"
fi

DEFAULT_TOPOLOGY_YAML=""
if [[ -n "${CHIP_SIZE}" ]]; then
  DEFAULT_TOPOLOGY_YAML="config/example/topologies/square-lattice-mux-${CHIP_SIZE}.yaml"
fi
TOPOLOGY_YAML=${TOPOLOGY_YAML:-${DEFAULT_TOPOLOGY_YAML}}

echo "Generating device topology from ${CALIB_NOTE_PATH}"

args=(
  -m device_gateway.tool.qubex_device_topology_generator
  --calib-note "${CALIB_NOTE_PATH}"
  --request-json "${REQUEST_JSON}"
  --params-dir "${PARAMS_DIR}"
  --output-json "${OUTPUT_JSON}"
  --output-png "${OUTPUT_PNG}"
)

if [[ -n "${TOPOLOGY_YAML}" && -f "${TOPOLOGY_YAML}" ]]; then
  args+=(--topology-yaml "${TOPOLOGY_YAML}")
elif [[ -d "${QDASH_REPO}/config/domain/topologies" ]]; then
  args+=(--qdash-repo "${QDASH_REPO}")
fi

uv run "${args[@]}"

echo "Generated ${OUTPUT_JSON}"
echo "Generated ${OUTPUT_PNG}"
