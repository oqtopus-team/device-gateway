import logging
import math
from typing import TYPE_CHECKING

import stim
from qiskit import QuantumCircuit as QiskitQuantumCircuit

if TYPE_CHECKING:
    from device_gateway.plugins.stim.backend import StimBackend

logger = logging.getLogger(__name__)

# Single-qubit Clifford gates: Qiskit instruction name -> stim gate name
_SINGLE_QUBIT_GATES = {
    "x": "X",
    "h": "H",
    "sx": "SQRT_X",
    "z": "Z",
}

# Two-qubit Clifford gates: Qiskit instruction name -> stim gate name
_TWO_QUBIT_GATES = {
    "cx": "CX",
}

# Instructions that carry no gate to apply to the stim circuit itself.
# Measurement is appended by the backend after all gates (end-of-circuit sampling),
# matching the qulacs backend semantics.
_NON_GATE_INSTRUCTIONS = {"measure", "barrier", "delay"}

# Qiskit rz angles that map exactly onto Clifford gates.
# rz(pi/2) -> S, rz(-pi/2) -> S_DAG, rz(pi) -> Z (also rz(-pi) -> Z).
_RZ_ANGLE_TOLERANCE = 1e-9


def _rz_clifford_gate(angle: float) -> str | None:
    """Map a Qiskit rz rotation angle to an equivalent stim Clifford gate.

    Returns the stim gate name for Clifford angles (pi/2, -pi/2, pi), or None
    for any other (non-Clifford) angle, which the caller ignores.
    """
    if math.isclose(angle, math.pi / 2, abs_tol=_RZ_ANGLE_TOLERANCE):
        return "S"
    if math.isclose(angle, -math.pi / 2, abs_tol=_RZ_ANGLE_TOLERANCE):
        return "S_DAG"
    if math.isclose(angle, math.pi, abs_tol=_RZ_ANGLE_TOLERANCE) or math.isclose(
        angle, -math.pi, abs_tol=_RZ_ANGLE_TOLERANCE
    ):
        return "Z"
    return None


class StimCompiler:
    """Compiles a Qiskit circuit into a stim Clifford circuit.

    stim is a Clifford-only simulator: non-Clifford gates (e.g. t, rx, ry, rz
    with a non-Clifford angle) are not supported. Rather than failing the job,
    any unsupported instruction is logged as a warning and ignored so the
    remaining Clifford gates still produce a valid result.
    """

    def __init__(self, backend: "StimBackend"):
        """Initialize the compiler with backend.

        Args:
            backend: Backend to compile the circuit for
        """
        self._backend = backend

    def compile(self, qc: QiskitQuantumCircuit) -> stim.Circuit:
        """Compile a Qiskit circuit to a stim circuit.

        Args:
            qc: Qiskit quantum circuit to compile

        Returns:
            Compiled stim circuit containing only the Clifford gates. Measurement
            instructions are not appended here; the backend adds them at the end.

        Raises:
            KeyError: If a qubit index is not present in the device topology.
        """
        circuit = stim.Circuit()

        for instruction in qc.data:
            name = instruction.name
            physical_label = self._backend.physical_label(
                qc.find_bit(instruction.qubits[0]).index
            )
            index = self._backend.physical_label_to_physical_index[physical_label]

            if name in _SINGLE_QUBIT_GATES:
                logger.debug(f"Applying {name} gate: Physical qubit: {physical_label}")
                circuit.append(_SINGLE_QUBIT_GATES[name], [index])
            elif name in _TWO_QUBIT_GATES:
                target_label = self._backend.physical_label(
                    qc.find_bit(instruction.qubits[1]).index
                )
                target_index = self._backend.physical_label_to_physical_index[
                    target_label
                ]
                logger.debug(
                    f"Applying {name} gate: Physical qubits: {physical_label} -> {target_label}"
                )
                circuit.append(_TWO_QUBIT_GATES[name], [index, target_index])
            elif name == "rz":
                angle = instruction.params[0]
                clifford_gate = _rz_clifford_gate(float(angle))
                if clifford_gate is None:
                    logger.warning(
                        f"Unsupported instruction: rz({angle}) on "
                        f"Physical qubit: {physical_label}. Ignoring."
                    )
                    continue
                logger.debug(
                    f"Applying rz({angle}) gate as {clifford_gate}: "
                    f"Physical qubit: {physical_label}"
                )
                circuit.append(clifford_gate, [index])
            elif name in _NON_GATE_INSTRUCTIONS:
                pass
            else:
                logger.warning(
                    f"Unsupported instruction: {name} on "
                    f"Physical qubit: {physical_label}. Ignoring."
                )

        return circuit
