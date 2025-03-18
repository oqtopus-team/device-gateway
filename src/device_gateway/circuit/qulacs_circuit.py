"""Qulacs circuit implementation."""

import logging

from qiskit import QuantumCircuit as QiskitQuantumCircuit
from qulacs import QuantumCircuit as QulacsQuantumCircuit

from device_gateway.backend.qulacs_backend import QulacsBackend
from device_gateway.circuit.base_circuit import BaseCircuit
from device_gateway.circuit.gate_set import SUPPORTED_GATES

logger = logging.getLogger("device_gateway")


class QulacsCircuit(BaseCircuit):
    """Qulacs circuit implementation."""

    def __init__(self, backend: QulacsBackend):
        """Initialize the circuit with backend.

        Args:
            backend: Backend to execute the circuit on
        """
        self._backend = backend

    def cx(self, circuit: QulacsQuantumCircuit, control: str, target: str):
        """Apply CX gate."""
        if target not in self._backend.qubits or control not in self._backend.qubits:
            logger.error(f"Invalid qubits for CNOT: {control}, {target}")
            raise ValueError(f"Invalid qubits for CNOT: {control}, {target}")
        logger.debug(
            f"Applying CX gate: {self._backend.virtual_qubit(control)} -> {self._backend.virtual_qubit(target)}, Physical qubits: {control} -> {target}"
        )
        circuit.add_CNOT_gate(
            self._backend.physical_virtual_qubits[control],
            self._backend.physical_virtual_qubits[target],
        )
        return circuit

    def sx(self, circuit: QulacsQuantumCircuit, target: str):
        """Apply SX gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.debug(
            f"Applying SX gate: {self._backend.virtual_qubit(target)}, Physical qubit: {target}"
        )
        new_circuit = circuit.copy()
        new_circuit.add_sqrtX_gate(self._backend.physical_virtual_qubits[target])
        return new_circuit

    def x(self, circuit: QulacsQuantumCircuit, target: str):
        """Apply X gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.debug(
            f"Applying X gate: {self._backend.virtual_qubit(target)}, Physical qubit: {target}"
        )
        circuit.add_X_gate(self._backend.physical_virtual_qubits[target])
        return circuit

    def rz(self, circuit: QulacsQuantumCircuit, target: str, angle: float):
        """Apply RZ gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.debug(
            f"Applying RZ gate: {self._backend.virtual_qubit(target)}, Physical qubit: {target}, angle={angle}"
        )
        new_circuit = circuit.copy()
        new_circuit.add_RZ_gate(
            self._backend.physical_virtual_qubits[target], -1 * angle
        )
        return new_circuit

    def compile(self, qc: QiskitQuantumCircuit) -> QulacsQuantumCircuit:
        """Compile a Qiskit circuit to a Qulacs circuit.

        Args:
            qc: Qiskit quantum circuit to compile

        Returns:
            Compiled Qulacs quantum circuit

        Raises:
            ValueError: If an unsupported instruction is encountered
        """
        circuit = QulacsQuantumCircuit(qc.num_qubits)

        for instruction in qc.data:
            name = instruction.name
            if name not in SUPPORTED_GATES:
                logger.error(f"Unsupported instruction: {name}")
                raise ValueError(f"Unsupported instruction: {name}")

            virtual_index = qc.find_bit(instruction.qubits[0]).index
            physical_label = self._backend.physical_qubit(virtual_index)

            if name == "x":
                circuit = self.x(circuit, physical_label)
            elif name == "sx":
                circuit = self.sx(circuit, physical_label)
            elif name == "rz":
                angle = instruction.params[0]
                circuit = self.rz(circuit, physical_label, angle)
            elif name == "cx":
                virtual_target_index = qc.find_bit(instruction.qubits[1]).index
                physical_target_label = self._backend.physical_qubit(
                    virtual_target_index
                )
                circuit = self.cx(circuit, physical_label, physical_target_label)
            else:
                pass

        return circuit
