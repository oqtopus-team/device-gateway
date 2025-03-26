SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

.PHONY: lint
lint:
	buf lint

.PHONY: generate-qpu
generate-qpu:
	buf generate --template buf.gen.qpu.yaml
