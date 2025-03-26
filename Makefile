SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

PROTO_URL := https://raw.githubusercontent.com/oqtopus-team/oqtopus-engine/main/spec/proto/qpu_interface/v1/qpu.proto
SPEC_DIR := spec
PROTO_FILE := $(SPEC_DIR)/qpu.proto

.PHONY: proto-download proto-generate proto-clean

proto-download: ## Download proto file from oqtopus-engine
	@echo "Downloading proto file..."
	@curl -s $(PROTO_URL) -o $(PROTO_FILE)

proto-generate: proto-download ## Generate gRPC code from proto file
	@echo "Generating gRPC code..."
	@cd $(SPEC_DIR) && MAKE generate-qpu

list-service: ## List all services
	@grpcurl -plaintext localhost:50051 list

list-method: ## List all methods
	@grpcurl -plaintext localhost:50051 list qpu_interface.v1.QpuServices

job:
	@grpcurl -plaintext -d '{ \
		"job_id": "test_job", \
		"shots": 1000, \
		"program": "OPENQASM 3;include \"stdgates.inc\";qubit[2] q;bit[2] c;rz(1.5707963267948932) q[0];sx q[0];rz(1.5707963267948966) q[0];cx q[0], q[1];x q[1];c[0] = measure q[0];c[1] = measure q[1];" \
	}' localhost:50051 qpu_interface.v1.QpuService.CallJob


run:
	@uv run src/device_gateway/service.py -c config/config.yaml -l config/logging.yaml

generate-topology:
	@uv run tool/topology_generator.py

test:
	@uv run pytest


docs:
	@uv run mkdocs build

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(filter-out .env,$(MAKEFILE_LIST)) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
