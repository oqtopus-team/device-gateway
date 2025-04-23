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
        logger.info(
            f"Applying CX gate: {self._backend.physical_index(control)} -> {self._backend.physical_index(target)}, Physical qubits: {control} -> {target}"
        )
        with PulseSchedule([control, target]) as ps:
            ps.call(self._backend._experiment.cx(control, target))
        return ps

    def sx(self, target: str):
        """Apply SX gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.info(
            f"Applying SX gate: {self._backend.physical_index(target)}, Physical qubit: {target}"
        )
        with PulseSchedule([target]) as ps:
            ps.add(target, self._backend._experiment.x90(target))
        return ps

    def x(self, target: str):
        """Apply X gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.info(
            f"Applying X gate: {self._backend.physical_index(target)}, Physical qubit: {target}"
        )
        with PulseSchedule([target]) as ps:
            ps.add(target, self._backend._experiment.x180(target))
        return ps

    def rz(self, target: str, angle: float):
        """Apply RZ gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.info(
            f"Applying RZ gate: {self._backend.physical_index(target)}, Physical qubit: {target}, angle={angle}"
        )
        with PulseSchedule([target]) as ps:
            ps.add(target, VirtualZ(angle))
        return ps

    def compile(self, qc: QiskitQuantumCircuit) -> PulseSchedule:
        """Compile a Qiskit circuit to a  Qubex pulse scheduler.

        Args:
            qc: Qiskit quantum circuit to compile

        Returns:
            Compiled Qulacs quantum circuit

        Raises:
            ValueError: If an unsupported instruction is encountered
        """
        used_physical_qubits: set[str] = set()
        used_physical_couplings: set[str] = set()
        logger.info(f"physical_map: {self._backend.physical_map}")
        classical_bit_mapping = {}

        pulse_scheduler = []
        for instruction in qc.data:
            name = instruction.name
            if name not in SUPPORTED_GATES:
                logger.error(f"Unsupported instruction: {name}")
                raise ValueError(f"Unsupported instruction: {name}")

            physical_index = qc.find_bit(instruction.qubits[0]).index
            physical_label = self._backend.physical_label(physical_index)
            used_physical_qubits.add(physical_label)

            if name == "x":
                pulse_scheduler.append(self.x(physical_label))
            elif name == "sx":
                pulse_scheduler.append(self.sx(physical_label))
            elif name == "rz":
                angle = instruction.params[0]
                pulse_scheduler.append(self.rz(physical_label, angle))
            elif name == "cx":
                physical_target_index = qc.find_bit(instruction.qubits[1]).index
                physical_target_label = self._backend.physical_label(
                    physical_target_index
                )
                pulse_scheduler.append(self.cx(physical_label, physical_target_label))
                coupling = f"{physical_label}-{physical_target_label}"
                used_physical_qubits.add(physical_target_label)
                used_physical_couplings.add(coupling)
            elif name == "measure":
                # TODO: intermediate measurement or partial measurement
                virtual_index = qc.find_bit(instruction.clbits[0]).index
                physical_index = qc.find_bit(instruction.qubits[0]).index
                classical_bit_mapping[virtual_index] = physical_index
                logger.info(
                    f"virtual qubit: {virtual_index} -> physical index: {physical_index} -> physical label: {self._backend.physical_label(physical_index)}"
                )
            else:
                pass
        classical_registers = []
        # qubex bit mapping is inversed of Qiskit e.g. qubex: | q0, q1, q2 >, qiskit: | q2, q1, q0 >
        inversed_classical_bit_mapping = sorted(
            classical_bit_mapping.items(), key=lambda x: x[0], reverse=True
        )
        for virtual, physical in inversed_classical_bit_mapping:
            classical_registers.append(self._backend.physical_label(physical))
        self._backend.classical_registers = classical_registers

        with PulseSchedule(
            list(used_physical_qubits) + list(used_physical_couplings)
        ) as circuit:
            for ps in pulse_scheduler:
                circuit.call(ps)
                circuit.barrier()
        return circuit
