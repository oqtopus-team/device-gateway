import logging
from typing import TYPE_CHECKING

from qiskit import QuantumCircuit as QiskitQuantumCircuit
from qulacs import QuantumCircuit as QulacsQuantumCircuit

if TYPE_CHECKING:
    from device_gateway.plugins.qulacs.backend import QulacsBackend

logger = logging.getLogger(__name__)

# Single-qubit gates with no parameters: Qiskit instruction name -> QulacsQuantumCircuit method name
_SINGLE_QUBIT_GATES = {
    "x": "add_X_gate",
    "y": "add_Y_gate",
    "z": "add_Z_gate",
    "h": "add_H_gate",
    "s": "add_S_gate",
    "sdg": "add_Sdag_gate",
    "t": "add_T_gate",
    "tdg": "add_Tdag_gate",
    "sx": "add_sqrtX_gate",
    "sxdg": "add_sqrtXdag_gate",
}

# Single-qubit rotation gates: Qulacs rotates the opposite direction of Qiskit
# for the same angle, so the angle is negated (verified empirically against
# qiskit.quantum_info.Statevector for rx/ry/rz).
_SINGLE_QUBIT_ROTATION_GATES = {
    "rx": "add_RX_gate",
    "ry": "add_RY_gate",
    "rz": "add_RZ_gate",
}

# Two-qubit gates with no parameters: Qiskit instruction name -> QulacsQuantumCircuit method name
_TWO_QUBIT_GATES = {
    "cx": "add_CNOT_gate",
    "cz": "add_CZ_gate",
    "swap": "add_SWAP_gate",
}

# Instructions that carry no gate to apply to the Qulacs circuit itself.
_NON_GATE_INSTRUCTIONS = {"measure", "barrier", "delay"}


class QulacsCompiler:
    """Compiles a Qiskit circuit into a Qulacs circuit."""

    def __init__(self, backend: "QulacsBackend"):
        """Initialize the compiler with backend.

        Args:
            backend: Backend to compile the circuit for
        """
        self._backend = backend

    def compile(self, qc: QiskitQuantumCircuit) -> QulacsQuantumCircuit:
        """Compile a Qiskit circuit to a Qulacs circuit.

        Args:
            qc: Qiskit quantum circuit to compile

        Returns:
            Compiled Qulacs quantum circuit

        Raises:
            ValueError: If an unsupported or unrecognized instruction is encountered
        """
        circuit = QulacsQuantumCircuit(qc.num_qubits)

        for instruction in qc.data:
            name = instruction.name
            if (
                self._backend.supported_gates is not None
                and name not in self._backend.supported_gates
            ):
                logger.error(f"Unsupported instruction: {name}")
                raise ValueError(f"Unsupported instruction: {name}")

            physical_index = qc.find_bit(instruction.qubits[0]).index
            physical_label = self._backend.physical_label(physical_index)
            index = self._backend.physical_label_to_physical_index[physical_label]

            if name in _SINGLE_QUBIT_GATES:
                logger.debug(f"Applying {name} gate: Physical qubit: {physical_label}")
                getattr(circuit, _SINGLE_QUBIT_GATES[name])(index)
            elif name in _SINGLE_QUBIT_ROTATION_GATES:
                angle = instruction.params[0]
                logger.debug(
                    f"Applying {name} gate: Physical qubit: {physical_label}, angle={angle}"
                )
                # Qiskit and Qulacs use opposite sign conventions for rotation
                # angles, so the angle must be negated here.
                getattr(circuit, _SINGLE_QUBIT_ROTATION_GATES[name])(index, -angle)
            elif name in ("p", "u1"):
                lam = instruction.params[0]
                logger.debug(
                    f"Applying {name} gate: Physical qubit: {physical_label}, lambda={lam}"
                )
                circuit.add_U1_gate(index, lam)
            elif name == "u2":
                phi, lam = instruction.params
                logger.debug(
                    f"Applying u2 gate: Physical qubit: {physical_label}, phi={phi}, lambda={lam}"
                )
                circuit.add_U2_gate(index, phi, lam)
            elif name in ("u", "u3"):
                theta, phi, lam = instruction.params
                logger.debug(
                    f"Applying {name} gate: Physical qubit: {physical_label}, "
                    f"theta={theta}, phi={phi}, lambda={lam}"
                )
                circuit.add_U3_gate(index, theta, phi, lam)
            elif name in _TWO_QUBIT_GATES:
                physical_target_index = qc.find_bit(instruction.qubits[1]).index
                physical_target_label = self._backend.physical_label(
                    physical_target_index
                )
                target_index = self._backend.physical_label_to_physical_index[
                    physical_target_label
                ]
                logger.debug(
                    f"Applying {name} gate: Physical qubits: {physical_label} -> {physical_target_label}"
                )
                getattr(circuit, _TWO_QUBIT_GATES[name])(index, target_index)
            elif name in _NON_GATE_INSTRUCTIONS:
                pass
            else:
                logger.error(f"Unrecognized instruction: {name}")
                raise ValueError(f"Unrecognized instruction: {name}")

        return circuit
