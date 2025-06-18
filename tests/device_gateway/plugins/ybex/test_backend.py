import json

import pytest

from device_gateway.plugins.ybex.backend import YbexBackend

device_topology = """{
  "name": "anemone",
  "device_id": "anemone",
  "qubits": [
    {
      "id": 0,
      "physical_id": 0
    },
    {
      "id": 1,
      "physical_id": 1
    },
    {
      "id": 2,
      "physical_id": 2
    },
    {
      "id": 3,
      "physical_id": 3
    }
  ],
  "couplings": [
    {
      "control": 0,
      "target": 1
    },
    {
      "control": 0,
      "target": 2
    },
    {
      "control": 3,
      "target": 1
    },
    {
      "control": 3,
      "target": 2
    }
  ],
  "calibrated_at": "2025-04-20T10:03:16.755183Z"
}
"""

program = """
OPENQASM 3;
include "stdgates.inc";
bit[1] c;
rx(1.0) $0;
rx(0.57) $0;
c[0] = measure $0;
"""


class TestYbexBackendBackend:
    def test_execute(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = YbexBackend(
            {
                "plugin": {
                    "backend": {
                        "command": "uv run python tests/device_gateway/plugins/ybex/external_program_mock.py {shots} {angle}"
                    }
                }
            }
        )

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert isinstance(counts, dict)
        assert "0" in counts
        assert "1" in counts
        assert message == "job is succeeded"

    def test_execute__raise(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = YbexBackend(
            {
                "plugin": {
                    "backend": {
                        "command": "uv run python tests/device_gateway/plugins/ybex/external_program_external_program_raise.py {shots} {angle}"
                    }
                }
            }
        )

        # Act
        with pytest.raises(RuntimeError):
            backend.execute(program, shots=1000)

    def test_execute__invalid_result(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = YbexBackend(
            {
                "plugin": {
                    "backend": {
                        "command": "uv run python tests/device_gateway/plugins/ybex/external_program_invalid_result.py {shots} {angle}"
                    }
                }
            }
        )

        # Act
        with pytest.raises(json.JSONDecodeError):
            backend.execute(program, shots=1000)
