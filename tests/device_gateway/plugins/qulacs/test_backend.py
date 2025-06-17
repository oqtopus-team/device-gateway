import json

from device_gateway.plugins.qulacs.backend import QulacsBackend

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


class TestQulacsBackend:
    def test_execute(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend({})
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[2] c;
            rz(1.5707963267948932) $0;
            sx $0;
            rz(1.5707963267948966) $0;
            cx $0, $1;
            c[0] = measure $0;
            c[1] = measure $1;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert isinstance(counts, dict)
        assert "00" in counts
        assert "11" in counts
        assert message == "job is succeeded"

    def test_execute__sparse_circuit(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend({})
        # qubit $1 is not used in this circuit
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[2] c;
            rz(1.5707963267948932) $0;
            sx $0;
            rz(1.5707963267948966) $0;
            cx $0, $2;
            c[0] = measure $0;
            c[1] = measure $2;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert isinstance(counts, dict)
        assert "11" in counts
        assert message == "job is succeeded"

    def test_execute__not_assigned_c0(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend({})
        # c[0] is not assigned, so its value is 0
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[2] c;
            x $0;
            c[1] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert isinstance(counts, dict)
        assert "10" in counts
        assert message == "job is succeeded"

    def test_execute__no_operation_q1(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend({})
        # No operation is applied to $1, so its value is 0
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[2] c;
            rz(1.5707963267948932) $0;
            sx $0;
            rz(1.5707963267948966) $0;
            c[0] = measure $0;
            c[1] = measure $1;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert isinstance(counts, dict)
        assert "00" in counts
        assert "01" in counts
        assert message == "job is succeeded"

    def test_execute__not_assigned_c1_and_no_operation_q1(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend({})
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[2] c;
            rz(1.5707963267948932) $0;
            sx $0;
            rz(1.5707963267948966) $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert isinstance(counts, dict)
        assert "00" in counts
        assert "01" in counts
        assert message == "job is succeeded"

    def test_execute__measure_selected_qubit(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend({})
        # 2-qubit circuit with only one measurement
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            x $1;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert isinstance(counts, dict)
        assert "0" in counts
        assert message == "job is succeeded"
