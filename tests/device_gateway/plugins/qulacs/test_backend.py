import json

import pytest

from device_gateway.plugins.qulacs.backend import QulacsBackend

SUPPORTED_GATES = [
    "x",
    "y",
    "z",
    "h",
    "s",
    "sdg",
    "t",
    "tdg",
    "sx",
    "sxdg",
    "rx",
    "ry",
    "rz",
    "p",
    "u1",
    "u2",
    "u3",
    "cx",
    "cz",
    "swap",
    "measure",
    "barrier",
    "delay",
]

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
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
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
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
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
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
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
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
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
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
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
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
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

    def test_execute__qubit_index_out_of_topology_raises(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # The 4-qubit topology only defines ids 0-3, so $4 is out of range
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            x $4;
            c[0] = measure $4;
        """

        # Act & Assert
        with pytest.raises(KeyError):
            backend.execute(program, shots=1000)

    def test_execute__h_gate_creates_superposition(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            h $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=2000)

        # Assert
        assert "0" in counts
        assert "1" in counts
        assert message == "job is succeeded"

    def test_execute__u3_pi_flips_qubit(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # u3(pi, 0, 0) is equivalent to an X gate
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            u3(3.14159265358979, 0, 0) $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__swap_gate_moves_excitation(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # $0 is excited then swapped into $1, so measuring $1 should read 1
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            x $0;
            swap $0, $1;
            c[0] = measure $1;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__cz_with_hadamards_behaves_as_cx(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # H-CZ-H on the target is equivalent to CX; with control ($0) set to 1,
        # the target ($1) must flip to 1 deterministically.
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            x $0;
            h $1;
            cz $0, $1;
            h $1;
            c[0] = measure $1;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__unrecognized_instruction_raises(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        # plugin_config omitted so the compiler's own dispatch is exercised
        # directly, rather than being rejected earlier by the config check.
        backend = QulacsBackend("simulator", {})
        # ccx (Toffoli) is a valid stdgate, but has no Qulacs dispatch entry
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            ccx $0, $1, $2;
            c[0] = measure $0;
        """

        # Act & Assert
        with pytest.raises(ValueError, match="Unrecognized instruction"):
            backend.execute(program, shots=1000)

    def test_execute__y_gate_flips_qubit(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            y $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__z_gate_via_hadamard_sandwich(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # H-Z-H is equivalent to X
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            h $0;
            z $0;
            h $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__s_gate_squared_is_z(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # S*S is equivalent to Z; sandwiched by H this behaves as X
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            h $0;
            s $0;
            s $0;
            h $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__sdg_gate_squared_is_z(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # Sdg*Sdg is equivalent to Z; sandwiched by H this behaves as X
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            h $0;
            sdg $0;
            sdg $0;
            h $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__t_gate_to_the_fourth_is_z(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # T^4 is equivalent to Z; sandwiched by H this behaves as X
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            h $0;
            t $0;
            t $0;
            t $0;
            t $0;
            h $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__tdg_gate_to_the_fourth_is_z(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # Tdg^4 is equivalent to Z; sandwiched by H this behaves as X
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            h $0;
            tdg $0;
            tdg $0;
            tdg $0;
            tdg $0;
            h $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__sxdg_undoes_sx(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # SX followed by its inverse SXDG cancels out, leaving only the X applied first.
        # stdgates.inc has no direct "sxdg" call, so the inverse modifier is used
        # (this still compiles to a plain "sxdg" instruction).
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            x $0;
            sx $0;
            inv @ sx $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__p_gate_squared_is_z(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # p(pi/2) is equivalent to S; applying it twice sandwiched by H behaves as X
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            h $0;
            p(1.5707963267948966) $0;
            p(1.5707963267948966) $0;
            h $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__u1_gate_squared_is_z(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # u1(pi/2) is equivalent to S; applying it twice sandwiched by H behaves as X
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            h $0;
            u1(1.5707963267948966) $0;
            u1(1.5707963267948966) $0;
            h $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__u2_gate_is_hadamard(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # u2(0, pi) is equivalent to H; applying it twice is the identity
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            u2(0, 3.14159265358979) $0;
            u2(0, 3.14159265358979) $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"0": 1000}
        assert message == "job is succeeded"

    def test_execute__ry_rotation_sign_matches_qiskit(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # ry(pi/2)|0> = |+>, so a following H deterministically returns to |0>.
        # This regresses if Qulacs's angle-negation convention for ry is wrong.
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            ry(1.5707963267948966) $0;
            h $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"0": 1000}
        assert message == "job is succeeded"

    def test_execute__rx_rotation_sign_matches_qiskit(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        # rx(pi/2)|0> is the -1 eigenstate of Y; Sdg-then-H deterministically maps
        # it to |1>. This regresses if Qulacs's angle-negation convention for rx is wrong.
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            rx(1.5707963267948966) $0;
            sdg $0;
            h $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__barrier_and_delay_are_no_ops(self, mocker) -> None:
        # Arrange
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        backend = QulacsBackend(
            "simulator",
            {},
            {"supported_gates": SUPPORTED_GATES},
        )
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            x $0;
            barrier $0;
            delay[100ns] $0;
            c[0] = measure $0;
        """

        # Act
        counts, message = backend.execute(program, shots=1000)

        # Assert
        assert counts == {"1": 1000}
        assert message == "job is succeeded"
