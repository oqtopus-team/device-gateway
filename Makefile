SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

PROTO_URL := https://raw.githubusercontent.com/oqtopus-team/oqtopus-engine/main/spec/proto/qpu_interface/v1/qpu.proto
SPEC_DIR := spec
PROTO_FILE := $(SPEC_DIR)/qpu.proto

.PHONY: proto-download proto-generate, generate-config, generate-deveice-topology, download-qubex-config, job, run, test, docs

proto-download: ## Download proto file from oqtopus-engine
	@echo "Downloading proto file..."
	@curl -s $(PROTO_URL) -o $(PROTO_FILE)

proto-generate: proto-download ## Generate gRPC code from proto file
	@echo "Generating gRPC code..."
	@cd $(SPEC_DIR) && MAKE generate-qpu

run:
	@uv run src/device_gateway/service.py -c config/config.yaml -l config/logging.yaml

test:
	@uv run pytest


docs:
	@uv run mkdocs build

generate-config: ## Generate config
	@echo "Generating config..."
	@bash scripts/generate_config.sh
	@echo "Config generated."

generate-device-topology: ## Generate device topology
	@echo "Generating device topology..."
	@bash scripts/device_topology_generator.sh

download-qubex-config: ## Download qubex config
	@echo "Downloading qubex config..."
	@bash scripts/qubex_config_downloader.sh

change-status-to-active: ## Change status to active
	@echo "Changing status to active..."
	@bash scripts/change_status_to_active.sh
	@echo "Status changed to active."

change-status-to-inactive: ## Change status to inactive
	@echo "Changing status to inactive..."
	@bash scripts/change_status_to_inactive.sh
	@echo "Status changed to inactive."

change-status-to-maintenance: ## Change status to maintenance
	@echo "Changing status to maintenance..."
	@bash scripts/change_status_to_maintenance.sh
	@echo "Status changed to maintenance."

install-qubex:
	@echo "Installing qubex..."
	@uv sync --only-group qubex
	@echo "Qubex installed."

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(filter-out .env,$(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
