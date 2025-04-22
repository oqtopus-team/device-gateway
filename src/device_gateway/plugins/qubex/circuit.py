import logging

from qiskit import QuantumCircuit as QiskitQuantumCircuit
from qubex.pulse import PulseSchedule, VirtualZ

from device_gateway.core.base_circuit import BaseCircuit
from device_gateway.core.gate_set import SUPPORTED_GATES
from device_gateway.plugins.qubex.backend import QubexBackend

logger = logging.getLogger("device_gateway")


class QubexCircuit(BaseCircuit):
    """Qubex circuit implementation."""

    def __init__(self, backend: QubexBackend):
        """Initialize the circuit with backend.
        Args:
            backend: Backend to execute the circuit on
        """
        self._backend = backend

    def cx(self, control: str, target: str):
        """Apply CX gate."""
        if target not in self._backend.qubits or control not in self._backend.qubits:
            logger.error(f"Invalid qubits for CNOT: {control}, {target}")
            raise ValueError(f"Invalid qubits for CNOT: {control}, {target}")
        logger.debug(
            f"Applying CX gate: {self._backend.virtual_qubit(control)} -> {self._backend.virtual_qubit(target)}, Physical qubits: {control} -> {target}"
        )
        with PulseSchedule([control, target]) as ps:
            ps.call(self._backend._experiment.cx(control, target))
        return ps

    def sx(self, target: str):
        """Apply SX gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.debug(
            f"Applying SX gate: {self._backend.virtual_qubit(target)}, Physical qubit: {target}"
        )
        with PulseSchedule([target]) as ps:
            ps.add(target, self._backend._experiment.x90(target))
        return ps

    def x(self, target: str):
        """Apply X gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.debug(
            f"Applying X gate: {self._backend.virtual_qubit(target)}, Physical qubit: {target}"
        )
        with PulseSchedule([target]) as ps:
            ps.add(target, self._backend._experiment.x180(target))
        return ps

    def rz(self, target: str, angle: float):
        """Apply RZ gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.debug(
            f"Applying RZ gate: {self._backend.virtual_qubit(target)}, Physical qubit: {target}, angle={angle}"
        )
        with PulseSchedule([target]) as ps:
            ps.add(target, VirtualZ(angle))
        return ps

    def _used_physical_qubits_and_couplings(self, qc: QiskitQuantumCircuit):
        """Return the used physical qubits and couplings."""
        used_physical_qubits = set()
        used_physical_couplings = set()

        for instruction in qc.data:
            name = instruction.name
            if name not in SUPPORTED_GATES:
                logger.error(f"Unsupported instruction: {name}")
                raise ValueError(f"Unsupported instruction: {name}")

            virtual_index = qc.find_bit(instruction.qubits[0]).index
            physical_label = self._backend.physical_qubit(virtual_index)
            used_physical_qubits.add(physical_label)

            if name == "cx":
                virtual_target_index = qc.find_bit(instruction.qubits[1]).index
                physical_target_label = self._backend.physical_qubit(
                    virtual_target_index
                )
                used_physical_qubits.add(physical_target_label)
                coupling = f"{physical_label}-{physical_target_label}"
                used_physical_couplings.add(coupling)

        # Convert sets to sorted lists
        # Sort physical qubits based on their virtual qubit indices
        physical_to_virtual = self._backend.physical_virtual_qubits
        sorted_physical_qubits = sorted(
            list(used_physical_qubits), key=lambda x: physical_to_virtual[x]
        )
        sorted_physical_couplings = sorted(list(used_physical_couplings))

        return sorted_physical_qubits, sorted_physical_couplings

    def compile(self, qc: QiskitQuantumCircuit) -> PulseSchedule:
        """Compile a Qiskit circuit to a  Qubex pulse scheduler.

        Args:
            qc: Qiskit quantum circuit to compile

        Returns:
            Compiled Qulacs quantum circuit

        Raises:
            ValueError: If an unsupported instruction is encountered
        """
        used_physical_qubits, used_physical_couplings = (
            self._used_physical_qubits_and_couplings(qc)
        )
        logger.info(f"used_physical_qubits: {used_physical_qubits}")
        logger.info(f"used_physical_couplings: {used_physical_couplings}")
        logger.info(f"virtual_physical_map: {self._backend.virtual_physical_map}")

        pulse_scheduler = []
        for instruction in qc.data:
            name = instruction.name
            if name not in SUPPORTED_GATES:
                logger.error(f"Unsupported instruction: {name}")
                raise ValueError(f"Unsupported instruction: {name}")

            virtual_index = qc.find_bit(instruction.qubits[0]).index
            physical_label = self._backend.physical_qubit(virtual_index)

            if name == "x":
                pulse_scheduler.append(self.x(physical_label))
            elif name == "sx":
                pulse_scheduler.append(self.sx(physical_label))
            elif name == "rz":
                angle = instruction.params[0]
                pulse_scheduler.append(self.rz(physical_label, angle))
            elif name == "cx":
                virtual_target_index = qc.find_bit(instruction.qubits[1]).index
                physical_target_label = self._backend.physical_qubit(
                    virtual_target_index
                )
                pulse_scheduler.append(self.cx(physical_label, physical_target_label))
            else:
                pass
            with PulseSchedule(
                used_physical_qubits + used_physical_couplings
            ) as circuit:
                for ps in pulse_scheduler:
                    circuit.call(ps)
                    circuit.barrier()
        return circuit
