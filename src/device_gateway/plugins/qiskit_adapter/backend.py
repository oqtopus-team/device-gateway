"""Generic Qiskit backend adapter for Device Gateway.

This plugin lets Device Gateway host a Qiskit backend or a provider that
returns one. Device Gateway keeps the OQTOPUS service boundary while the loaded
Qiskit backend owns transpilation targets, validation, execution, and result
conversion.
"""

from __future__ import annotations

import logging
from typing import Any

from qiskit import transpile
from qiskit.qasm3 import loads

from device_gateway.core.base_backend import SUCCESS_MESSAGE, BaseBackend
from device_gateway.core.object_loader import load_object, resolve_references

logger = logging.getLogger("device_gateway")


class QiskitAdapterBackend(BaseBackend):
    """Device Gateway backend that delegates execution to a Qiskit backend."""

    def __init__(self, config: dict):
        super().__init__(config)
        plugin_config = config.get("plugin", {})
        self._qiskit_config = plugin_config.get(
            "qiskit_adapter",
            plugin_config.get("qiskit", {}),
        )
        self._backend = self._load_backend()

    def _get_circuit(self) -> Any:
        """Return the delegated Qiskit backend for compatibility hooks."""
        return self._backend

    def _execute(self, circuit: Any, shots: int = 1024) -> dict[str, int]:
        """Execute a Qiskit circuit on the delegated backend."""
        run_options = resolve_references(
            dict(self._qiskit_config.get("run_options", {}))
        )
        run_options["shots"] = shots
        job = self._backend.run(circuit, **run_options)
        result = job.result()
        counts = result.get_counts()
        if isinstance(counts, list):
            if len(counts) != 1:
                raise ValueError(
                    "Device Gateway CallJob expects one result count mapping, "
                    f"but Qiskit returned {len(counts)} mappings."
                )
            counts = counts[0]
        bit_count = max(
            getattr(circuit, "num_clbits", 0),
            getattr(circuit, "num_qubits", 0),
            1,
        )
        return {
            _format_count_key(str(key), bit_count): int(value)
            for key, value in counts.items()
        }

    def execute(self, program: str, shots: int = 1024) -> tuple[dict[str, int], str]:
        """Parse OpenQASM 3 and execute it through the configured Qiskit backend."""
        circuit = loads(program)
        compiled = self._transpile(circuit)
        self._validate(compiled)
        counts = self._execute(compiled, shots=shots)
        counts = self._remove_zero_values(counts)
        logger.info("counts=%s", counts)
        return counts, SUCCESS_MESSAGE

    def _transpile(self, circuit: Any) -> Any:
        transpile_options = self._qiskit_config.get("transpile_options")
        if transpile_options is False:
            return circuit
        options = resolve_references(dict(transpile_options or {}))
        return transpile(circuit, self._backend, **options)

    def _validate(self, circuit: Any) -> None:
        if not self._qiskit_config.get("validate", True):
            return
        validate = getattr(self._backend, "validate", None)
        if callable(validate):
            validate(circuit)

    def _load_backend(self) -> Any:
        backend_spec = self._qiskit_config.get("backend")
        provider_spec = self._qiskit_config.get("provider")
        if provider_spec:
            provider = load_object(provider_spec)
            backend = self._backend_from_provider(provider, backend_spec)
        elif backend_spec:
            backend = load_object(backend_spec)
        else:
            raise ValueError(
                "Qiskit adapter requires plugin.qiskit_adapter.backend or "
                "plugin.qiskit_adapter.provider configuration."
            )
        if not hasattr(backend, "run"):
            raise TypeError("Configured Qiskit backend must provide run(...).")
        return backend

    def _backend_from_provider(self, provider: Any, backend_spec: Any) -> Any:
        if backend_spec is None:
            method_name = "get_backend"
            kwargs = {}
        else:
            method_name = str(backend_spec.get("method", "get_backend"))
            kwargs = dict(backend_spec.get("kwargs", {}))
        backend_filters = dict(self._qiskit_config.get("backend_filters", {}))
        backend_name = self._qiskit_config.get("backend_name")
        if backend_name is not None:
            backend_filters.setdefault("name", backend_name)
        kwargs = resolve_references({**backend_filters, **kwargs})
        return getattr(provider, method_name)(**kwargs)


QiskitBackend = QiskitAdapterBackend


def _format_count_key(key: str, bit_count: int) -> str:
    """Return Device Gateway count keys as zero-padded bit strings."""
    if key.startswith("0x"):
        return format(int(key, 16), f"0{bit_count}b")
    return key.replace(" ", "")
