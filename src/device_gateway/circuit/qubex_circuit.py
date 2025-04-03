"""Qubex circuit implementation."""

import logging

import numpy as np
from qiskit import QuantumCircuit as QiskitQuantumCircuit
from qubex.pulse import PulseSchedule, VirtualZ

from device_gateway.backend.qubex_backend import QubexBackend
from device_gateway.circuit.base_circuit import BaseCircuit
from device_gateway.circuit.gate_set import SUPPORTED_GATES

logger = logging.getLogger("device_gateway")


class QubexCircuit(BaseCircuit):
    def __init__(self, backend: QubexBackend):
        self._backend = backend

    def cx(self, circuit: PulseSchedule, control: str, target: str):
        """Apply CX gate."""
        if target not in self._backend.qubits or control not in self._backend.qubits:
            logger.error(f"Invalid qubits for CNOT: {control}, {target}")
            raise ValueError(f"Invalid qubits for CNOT: {control}, {target}")
        logger.debug(
            f"Applying CX gate: {self._backend.virtual_qubit(control)} -> {self._backend.virtual_qubit(target)}, Physical qubits: {control} -> {target}"
        )
        cr_label = f"{control}-{target}"
        zx90_pulse = self._backend._experiment.zx90(control, target)
        x90_pulse = self._backend._experiment.drag_hpi_pulse.get(
            target, self._backend._experiment.hpi_pulse[target]
        )
        with PulseSchedule([control, cr_label, target]) as ps:
            ps.call(zx90_pulse)
            ps.add(control, VirtualZ(-np.pi / 2))
            ps.add(target, x90_pulse.scaled(-1))
        circuit.call(ps)
        return circuit

    def sx(self, circuit: PulseSchedule, target: str):
        """Apply SX gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.debug(
            f"Applying SX gate: {self._backend.virtual_qubit(target)}, Physical qubit: {target}"
        )
        x90_pulse = self._backend._experiment.drag_hpi_pulse.get(
            target, self._backend._experiment.drag_hpi_pulse[target]
        )
        with PulseSchedule([target]) as ps:
            ps.add(target, x90_pulse)
        circuit.call(ps)
        return circuit

    def x(self, circuit: PulseSchedule, target: str):
        """Apply X gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.debug(
            f"Applying X gate: {self._backend.virtual_qubit(target)}, Physical qubit: {target}"
        )
        x180_pulse = self._backend._experiment.drag_pi_pulse.get(
            target, self._backend._experiment.drag_pi_pulse[target]
        )
        with PulseSchedule([target]) as ps:
            ps.add(target, x180_pulse)
        circuit.call(ps)
        return circuit

    def rz(self, circuit: PulseSchedule, target: str, angle: float):
        """Apply RZ gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.debug(
            f"Applying RZ gate: {self._backend.virtual_qubit(target)}, Physical qubit: {target}, angle={angle}"
        )
        with PulseSchedule([target]) as ps:
            ps.add(target, VirtualZ(angle))
        circuit.call(ps)
        return circuit

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

        return used_physical_qubits, used_physical_couplings

    def compile(self, qc: QiskitQuantumCircuit) -> PulseSchedule:
        """Load a QASM 3 program and apply the corresponding gates to the circuit."""
        used_physical_qubits, used_physical_couplings = (
            self._used_physical_qubits_and_couplings(qc)
        )
        used_physical_qubits_list = list(used_physical_qubits)
        used_physical_couplings_list = list(used_physical_couplings)
        logger.info(f"used_physical_qubits: {used_physical_qubits_list}")
        logger.info(f"used_physical_couplings: {used_physical_couplings_list}")
        logger.info(f"virtual_physical_map: {self._backend._virtual_physical_map}")
        circuit = PulseSchedule(
            used_physical_qubits_list + used_physical_couplings_list
        )
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
            elif name == "measure":
                pass
            else:
                pass

        return circuit
