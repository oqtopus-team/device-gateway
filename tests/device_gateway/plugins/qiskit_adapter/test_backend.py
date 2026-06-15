from __future__ import annotations

from unittest.mock import MagicMock

from qiskit import QuantumCircuit

from device_gateway.plugins.qiskit_adapter.backend import (
    QiskitAdapterBackend,
    _format_count_key,
)


class FakeResult:
    def get_counts(self):
        return {"00": 4, "11": 6, "01": 0}


class FakeJob:
    def result(self):
        return FakeResult()


class FakeBackend:
    def __init__(self):
        self.run = MagicMock(return_value=FakeJob())
        self.validate = MagicMock()


class FakeBackendClass:
    pass


class FakeProvider:
    last_kwargs = None

    def __init__(self):
        self.backend = FakeBackend()

    def get_backend(self, **kwargs):
        type(self).last_kwargs = kwargs
        self.kwargs = kwargs
        return self.backend


def make_config():
    return {
        "device_info": {"provider_id": "oqtopus", "max_shots": 1000},
        "plugin": {
            "name": "qiskit_adapter",
            "qiskit_adapter": {
                "provider": {
                    "class": f"{__name__}.FakeProvider",
                },
                "backend": {
                    "method": "get_backend",
                    "kwargs": {
                        "backend_cls": {"class_ref": f"{__name__}.FakeBackendClass"}
                    },
                },
                "transpile_options": False,
                "run_options": {"memory": False},
            },
        },
    }


def test_qiskit_backend_executes_program_through_configured_provider():
    backend = QiskitAdapterBackend(make_config())
    program = """
OPENQASM 3;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
h q[0];
cx q[0], q[1];
c = measure q;
"""

    counts, message = backend.execute(program, shots=10)

    assert message == "job is succeeded"
    assert counts == {"00": 4, "11": 6}
    delegated = backend._backend
    delegated.validate.assert_called_once()
    delegated.run.assert_called_once()
    circuit = delegated.run.call_args.args[0]
    assert isinstance(circuit, QuantumCircuit)
    assert delegated.run.call_args.kwargs == {"memory": False, "shots": 10}
    assert FakeProvider.last_kwargs == {"backend_cls": FakeBackendClass}


def test_format_count_key_converts_hex_to_bitstring():
    assert _format_count_key("0x3", 4) == "0011"
    assert _format_count_key("0 1", 2) == "01"
