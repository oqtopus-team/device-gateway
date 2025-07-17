import logging
from typing import TYPE_CHECKING

from qiskit import QuantumCircuit as QiskitQuantumCircuit
from qubex.pulse import Blank, PulseSchedule, VirtualZ

from device_gateway.core.base_circuit import BaseCircuit
from device_gateway.core.gate_set import SUPPORTED_GATES

if TYPE_CHECKING:
    from device_gateway.plugins.qubex.backend import QubexBackend

logger = logging.getLogger("device_gateway")


class QubexCircuit(BaseCircuit):
    """Qubex circuit implementation."""

    def __init__(self, backend: "QubexBackend"):
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

    def barrier(self):
        """Apply barrier."""
        logger.info("Applying barrier")
        return "barrier"

    def get_delay_in_ns(self, delay_op, dt_in_ns: float = 2.0):
        import math

        """Convert delay to nanoseconds, rounded up to nearest multiple of dt_in_ns."""
        duration = float(delay_op.duration)
        unit = delay_op.unit

        # Convert duration to nanoseconds based on the unit
        if unit == "s":
            duration_ns = duration * 1e9
        elif unit == "ms":
            duration_ns = duration * 1e6
        elif unit == "us":
            duration_ns = duration * 1e3
        elif unit == "ns":
            duration_ns = duration
        elif unit == "dt":
            duration_ns = duration * dt_in_ns
        else:
            raise ValueError(f"Unsupported unit: {unit}")

        # 2ns is the minimum time step, round up to the nearest multiple of dt_in_ns
        rounded_ns = math.ceil(duration_ns / dt_in_ns) * dt_in_ns
        return rounded_ns

    def delay(self, target: str, duration: float):
        """Apply delay."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        if duration <= 0:
            logger.error(f"Invalid duration: {duration}")
            raise ValueError(f"Invalid duration: {duration}")
        logger.info(f"Applying delay for {duration} seconds")
        with PulseSchedule() as ps:
            ps.add(target, Blank(duration))
        return ps

    def rz_correction(self, target: str, angle: float):
        """Apply RZ correction."""
        if target not in self._backend.couplings:
            logger.error(f"Invalid coupling: {target}")
            raise ValueError(f"Invalid coupling: {target}")
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
            physical_label = self._backend.physical_label(virtual_index)
            used_physical_qubits.add(physical_label)

            if name == "cx":
                virtual_target_index = qc.find_bit(instruction.qubits[1]).index
                physical_target_label = self._backend.physical_label(
                    virtual_target_index
                )
                used_physical_qubits.add(physical_target_label)
                coupling = f"{physical_label}-{physical_target_label}"
                used_physical_couplings.add(coupling)

        # Convert sets to sorted lists
        # Sort physical qubits based on their virtual qubit indices
        physical_to_virtual = self._backend.physical_label_to_physical_index
        sorted_physical_qubits = sorted(
            list(used_physical_qubits), key=lambda x: physical_to_virtual[x]
        )
        sorted_physical_couplings = sorted(list(used_physical_couplings))

        return sorted_physical_qubits, sorted_physical_couplings

    def _cr_channel_has_this_target(
        self, target: str, used_physical_couplings: list[str]
    ):
        for coupling in used_physical_couplings:
            con, tar = coupling.split("-")
            if tar == target:
                return True
        return False

    def _cr_channels_of_this_target(
        self, target: str, used_physical_couplings: list[str]
    ) -> list[str]:
        channels: list[str] = []
        for coupling in used_physical_couplings:
            _, tar = coupling.split("-")
            if tar == target:
                channels.append(coupling)
        return channels

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
        logger.info(f"physical_map: {self._backend.physical_map}")
        classical_bit_mapping = {}

        pulse_scheduler = []
        for instruction in qc.data:
            name = instruction.operation.name
            if name not in SUPPORTED_GATES:
                logger.error(f"Unsupported instruction: {name}")
                raise ValueError(f"Unsupported instruction: {name}")

            physical_index = qc.find_bit(instruction.qubits[0]).index
            physical_label = self._backend.physical_label(physical_index)
            # used_physical_qubits.add(physical_label)

            if name == "x":
                pulse_scheduler.append(self.x(physical_label))
            elif name == "sx":
                pulse_scheduler.append(self.sx(physical_label))
            elif name == "rz":
                angle = instruction.params[0]
                ## lock with barrier for Virtual Z gate
                pulse_scheduler.append(self.barrier())
                pulse_scheduler.append(self.rz(physical_label, angle))
                # following pulse is for the correction of Virtual Z gate
                # we need to apply Virtual Z gate to cr channels, shared with same target
                if self._cr_channel_has_this_target(
                    target=physical_label,
                    used_physical_couplings=used_physical_couplings,
                ):
                    for cr_channel in self._cr_channels_of_this_target(
                        target=physical_label,
                        used_physical_couplings=used_physical_couplings,
                    ):
                        pulse_scheduler.append(self.rz_correction(cr_channel, angle))
                    pulse_scheduler.append(self.barrier())

            elif name == "cx":
                physical_target_index = qc.find_bit(instruction.qubits[1]).index
                physical_target_label = self._backend.physical_label(
                    physical_target_index
                )
                pulse_scheduler.append(self.cx(physical_label, physical_target_label))
            elif name == "measure":
                # TODO: intermediate measurement or partial measurement
                virtual_index = qc.find_bit(instruction.clbits[0]).index
                physical_index = qc.find_bit(instruction.qubits[0]).index
                classical_bit_mapping[virtual_index] = physical_index
                logger.info(
                    f"virtual qubit: {virtual_index} -> physical index: {physical_index} -> physical label: {self._backend.physical_label(physical_index)}"
                )
            elif name == "delay":
                duration = self.get_delay_in_ns(instruction.operation)
                pulse_scheduler.append(self.delay(physical_label, duration))
            elif name == "barrier":
                pulse_scheduler.append(self.barrier())
            else:
                logger.error(f"Unsupported instruction: {name}")
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
                if ps == "barrier":
                    circuit.barrier()
                else:
                    # logger.info(f"Adding pulse schedule: {ps}")
                    circuit.call(ps)

                # circuit.barrier()
        return circuit
