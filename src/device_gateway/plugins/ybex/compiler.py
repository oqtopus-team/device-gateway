import logging
from typing import TYPE_CHECKING

from qiskit import QuantumCircuit as QiskitQuantumCircuit

from device_gateway.plugins.ybex.circuit import SUPPORTED_GATES, YbexCircuit

if TYPE_CHECKING:
    from device_gateway.plugins.ybex.backend import YbexBackend

logger = logging.getLogger("device_gateway")


class YbexCompiler:
    """Ybex circuit compiler."""

    def __init__(self, backend: "YbexBackend"):
        self._backend = backend

    def compile(self, qc: QiskitQuantumCircuit) -> None:
        """Compile a Qiskit circuit to a Ybex circuit.

        Args:
            qc: Qiskit quantum circuit to compile

        Raises:
            ValueError: If an unsupported instruction is encountered

        """
        circuit = YbexCircuit(self._backend)

        for instruction in qc.data:
            name = instruction.name
            if name not in SUPPORTED_GATES:
                logger.error(f"Unsupported instruction: {name}")
                raise ValueError(f"Unsupported instruction: {name}")

            physical_index = qc.find_bit(instruction.qubits[0]).index
            physical_label = self._backend.physical_label(physical_index)

            if name == "rx":
                angle = instruction.params[0]
                circuit.rx(physical_label, angle)
            else:
                pass

        return circuit
