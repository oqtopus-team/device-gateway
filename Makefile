SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

PROTO_URL := https://raw.githubusercontent.com/oqtopus-team/oqtopus-engine/main/spec/proto/qpu_interface/v1/qpu.proto
SPEC_DIR := spec
PROTO_FILE := $(SPEC_DIR)/qpu.proto

.PHONY: proto-download proto-generate generate-config run format lint test verify docs-lint docs-build docs-serve generate-device-topology download-qubex-config change-status-to-active change-status-to-inactive change-status-to-maintenance install-qubex help

proto-download: ## Download proto file from oqtopus-engine
	@echo "Downloading proto file..."
	@curl -s $(PROTO_URL) -o $(PROTO_FILE)

proto-generate: proto-download ## Generate gRPC code from proto file
	@echo "Generating gRPC code..."
	@cd $(SPEC_DIR) && MAKE generate-qpu

run: ## Run the application
	@uv run src/device_gateway/service.py -c config/config.yaml -l config/logging.yaml

format: ## Run code formatting
	@uv run ruff check --fix
	@uv run ruff format

lint: ## Run linting
	@uv lock --check
	@uv run ruff check
	@uv run ruff format --check
	@uv run mypy

test: ## Run tests
	@uv run pytest

verify: format lint test ## Run all verification steps (formatting, linting, testing)

docs-lint: ## Run documentation linting
	@uv run pymarkdownlnt scan docs

docs-build: ## Build documentation
	@uv run mkdocs build

docs-serve: ## Serve documentation locally
	@uv run mkdocs serve

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
