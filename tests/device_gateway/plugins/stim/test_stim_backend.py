import json
import logging

import pytest

pytest.importorskip("stim")

from device_gateway.plugins.stim.backend import StimBackend

SUPPORTED_GATES = [
    "x",
    "h",
    "sx",
    "z",
    "rz",
    "cx",
    "measure",
    "barrier",
    "delay",
]

device_topology = """{
  "name": "anemone",
  "device_id": "anemone",
  "qubits": [
    {"id": 0, "physical_id": 0},
    {"id": 1, "physical_id": 1},
    {"id": 2, "physical_id": 2},
    {"id": 3, "physical_id": 3}
  ],
  "couplings": [
    {"control": 0, "target": 1},
    {"control": 0, "target": 2},
    {"control": 3, "target": 1},
    {"control": 3, "target": 2}
  ],
  "calibrated_at": "2025-04-20T10:03:16.755183Z"
}
"""


class TestStimBackend:
    def _backend(self, mocker, plugin_config=None):
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=json.loads(device_topology),
        )
        return StimBackend(
            "simulator",
            {},
            plugin_config
            if plugin_config is not None
            else {"supported_gates": SUPPORTED_GATES},
        )

    def test_execute__bell_state(self, mocker) -> None:
        backend = self._backend(mocker)
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[2] c;
            h $0;
            cx $0, $1;
            c[0] = measure $0;
            c[1] = measure $1;
        """

        counts, message = backend.execute(program, shots=1000)

        assert isinstance(counts, dict)
        assert "00" in counts
        assert "11" in counts
        assert message == "job is succeeded"

    def test_execute__x_gate_flips_qubit(self, mocker) -> None:
        backend = self._backend(mocker)
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            x $0;
            c[0] = measure $0;
        """

        counts, message = backend.execute(program, shots=1000)

        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__h_gate_creates_superposition(self, mocker) -> None:
        backend = self._backend(mocker)
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            h $0;
            c[0] = measure $0;
        """

        counts, message = backend.execute(program, shots=2000)

        assert "0" in counts
        assert "1" in counts
        assert message == "job is succeeded"

    def test_execute__sx_gate_creates_superposition(self, mocker) -> None:
        backend = self._backend(mocker)
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            sx $0;
            c[0] = measure $0;
        """

        counts, message = backend.execute(program, shots=2000)

        assert "0" in counts
        assert "1" in counts
        assert message == "job is succeeded"

    def test_execute__rz_half_pi_is_s(self, mocker) -> None:
        backend = self._backend(mocker)
        # rz(pi/2) behaves as S; S*S = Z, so H-Z-H = X -> |1>
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            h $0;
            rz(1.5707963267948966) $0;
            rz(1.5707963267948966) $0;
            h $0;
            c[0] = measure $0;
        """

        counts, message = backend.execute(program, shots=1000)

        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__z_gate_via_hadamard_sandwich(self, mocker) -> None:
        backend = self._backend(mocker)
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

        counts, message = backend.execute(program, shots=1000)

        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__unsupported_gate_logged_and_ignored(self, mocker, caplog) -> None:
        backend = self._backend(mocker)
        # t is a non-Clifford gate: it must be logged and ignored, not raise.
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            x $0;
            t $0;
            c[0] = measure $0;
        """

        with caplog.at_level(
            logging.WARNING, logger="device_gateway.plugins.stim.compiler"
        ):
            counts, message = backend.execute(program, shots=1000)

        assert counts == {"1": 1000}
        assert message == "job is succeeded"
        assert any(
            "Unsupported instruction: t" in record.message for record in caplog.records
        )

    def test_execute__non_clifford_rz_ignored(self, mocker) -> None:
        backend = self._backend(mocker)
        # rz with a non-Clifford angle (not pi/2 / -pi/2 / pi) must be ignored.
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            x $0;
            rz(0.3) $0;
            c[0] = measure $0;
        """

        counts, message = backend.execute(program, shots=1000)

        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__barrier_and_delay_are_no_ops(self, mocker) -> None:
        backend = self._backend(mocker)
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            x $0;
            barrier $0;
            delay[100ns] $0;
            c[0] = measure $0;
        """

        counts, message = backend.execute(program, shots=1000)

        assert counts == {"1": 1000}
        assert message == "job is succeeded"

    def test_execute__unassigned_clbit_is_zero(self, mocker) -> None:
        backend = self._backend(mocker)
        # c[0] is not assigned, so its value is 0; c[1] measures $0 (=1).
        # Count key ordering matches the qulacs backend.
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[2] c;
            x $0;
            c[1] = measure $0;
        """

        counts, message = backend.execute(program, shots=1000)

        assert counts == {"10": 1000}
        assert message == "job is succeeded"

    def test_execute__measure_selected_qubit(self, mocker) -> None:
        backend = self._backend(mocker)
        # 2-qubit circuit with only one measurement on qubit 1.
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            x $1;
            c[0] = measure $0;
        """

        counts, message = backend.execute(program, shots=1000)

        assert counts == {"0": 1000}
        assert message == "job is succeeded"

    def test_execute__qubit_index_out_of_topology_raises(self, mocker) -> None:
        backend = self._backend(mocker)
        # The 4-qubit topology only defines ids 0-3, so $4 is out of range.
        program = """
            OPENQASM 3;
            include "stdgates.inc";
            bit[1] c;
            x $4;
            c[0] = measure $4;
        """

        with pytest.raises(KeyError):
            backend.execute(program, shots=1000)
