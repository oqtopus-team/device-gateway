import logging
from typing import TYPE_CHECKING

from qiskit import QuantumCircuit as QiskitQuantumCircuit
from qulacs import QuantumCircuit as QulacsQuantumCircuit
from qulacs.gate import DepolarizingNoise, TwoQubitDepolarizingNoise

from device_gateway.core.base_circuit import BaseCircuit
from device_gateway.core.gate_set import SUPPORTED_GATES

if TYPE_CHECKING:
    from device_gateway.plugins.qulacs.backend import QulacsBackend

logger = logging.getLogger("device_gateway")


class QulacsCircuit(BaseCircuit):
    """Qulacs circuit implementation."""

    def __init__(self, backend: "QulacsBackend"):
        """Initialize the circuit with backend.

        Args:
            backend: Backend to execute the circuit on
        """
        self._backend = backend

    @property
    def _noise_model_config(self) -> dict:
        plugin_config = self._backend.config.get("plugin", {})
        return plugin_config.get("noise_model", {})

    def _noise_enabled(self) -> bool:
        return bool(self._noise_model_config.get("enabled", False))

    def _use_topology_fidelity(self) -> bool:
        return bool(self._noise_model_config.get("use_topology_fidelity", True))

    def _validate_probability(self, prob: float, name: str) -> float:
        if not (0.0 <= prob <= 1.0):
            raise ValueError(f"{name} must be in [0, 1], got {prob}")
        return prob

    def _single_qubit_noise_prob(self, target: str) -> float:
        configured_prob = self._noise_model_config.get("single_qubit_depolarizing")
        if configured_prob is not None:
            return self._validate_probability(
                float(configured_prob), "single_qubit_depolarizing"
            )

        if not self._use_topology_fidelity():
            return 0.0

        qubit_id = self._backend.physical_label_to_physical_index[target]
        for qubit in self._backend.device_topology.get("qubits", []):
            if qubit.get("id") == qubit_id:
                fidelity = float(qubit.get("fidelity", 1.0))
                return self._validate_probability(1.0 - fidelity, "qubit fidelity")
        return 0.0

    def _two_qubit_noise_prob(self, control: str, target: str) -> float:
        configured_prob = self._noise_model_config.get("two_qubit_depolarizing")
        if configured_prob is not None:
            return self._validate_probability(
                float(configured_prob), "two_qubit_depolarizing"
            )

        if not self._use_topology_fidelity():
            return 0.0

        control_id = self._backend.physical_label_to_physical_index[control]
        target_id = self._backend.physical_label_to_physical_index[target]
        couplings = self._backend.device_topology.get("couplings", [])
        for coupling in couplings:
            if (
                coupling.get("control") == control_id
                and coupling.get("target") == target_id
            ):
                fidelity = float(coupling.get("fidelity", 1.0))
                return self._validate_probability(1.0 - fidelity, "coupling fidelity")
        return 0.0

    def _add_single_qubit_noise(
        self, circuit: QulacsQuantumCircuit, target: str
    ) -> QulacsQuantumCircuit:
        if not self._noise_enabled():
            return circuit
        prob = self._single_qubit_noise_prob(target)
        if prob <= 0.0:
            return circuit
        circuit.add_gate(
            DepolarizingNoise(self._backend.physical_label_to_physical_index[target], prob)
        )
        return circuit

    def _add_two_qubit_noise(
        self, circuit: QulacsQuantumCircuit, control: str, target: str
    ) -> QulacsQuantumCircuit:
        if not self._noise_enabled():
            return circuit
        prob = self._two_qubit_noise_prob(control, target)
        if prob <= 0.0:
            return circuit
        circuit.add_gate(
            TwoQubitDepolarizingNoise(
                self._backend.physical_label_to_physical_index[control],
                self._backend.physical_label_to_physical_index[target],
                prob,
            )
        )
        return circuit

    def cx(self, circuit: QulacsQuantumCircuit, control: str, target: str):
        """Apply CX gate."""
        if target not in self._backend.qubits or control not in self._backend.qubits:
            logger.error(f"Invalid qubits for CNOT: {control}, {target}")
            raise ValueError(f"Invalid qubits for CNOT: {control}, {target}")
        logger.debug(
            f"Applying CX gate: {self._backend.physical_index(control)} -> {self._backend.physical_index(target)}, Physical qubits: {control} -> {target}"
        )
        circuit.add_CNOT_gate(
            self._backend.physical_label_to_physical_index[control],
            self._backend.physical_label_to_physical_index[target],
        )
        return circuit

    def sx(self, circuit: QulacsQuantumCircuit, target: str):
        """Apply SX gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.debug(
            f"Applying SX gate: {self._backend.physical_index(target)}, Physical qubit: {target}"
        )
        new_circuit = circuit.copy()
        new_circuit.add_sqrtX_gate(
            self._backend.physical_label_to_physical_index[target]
        )
        return new_circuit

    def x(self, circuit: QulacsQuantumCircuit, target: str):
        """Apply X gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.debug(
            f"Applying X gate: {self._backend.physical_index(target)}, Physical qubit: {target}"
        )
        circuit.add_X_gate(self._backend.physical_label_to_physical_index[target])
        return circuit

    def rz(self, circuit: QulacsQuantumCircuit, target: str, angle: float):
        """Apply RZ gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.debug(
            f"Applying RZ gate: {self._backend.physical_index(target)}, Physical qubit: {target}, angle={angle}"
        )
        new_circuit = circuit.copy()
        new_circuit.add_RZ_gate(
            self._backend.physical_label_to_physical_index[target], -1 * angle
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

            physical_index = qc.find_bit(instruction.qubits[0]).index
            physical_label = self._backend.physical_label(physical_index)

            if name == "x":
                circuit = self.x(circuit, physical_label)
                circuit = self._add_single_qubit_noise(circuit, physical_label)
            elif name == "sx":
                circuit = self.sx(circuit, physical_label)
                circuit = self._add_single_qubit_noise(circuit, physical_label)
            elif name == "rz":
                angle = instruction.params[0]
                circuit = self.rz(circuit, physical_label, angle)
                circuit = self._add_single_qubit_noise(circuit, physical_label)
            elif name == "cx":
                physical_target_index = qc.find_bit(instruction.qubits[1]).index
                physical_target_label = self._backend.physical_label(
                    physical_target_index
                )
                circuit = self.cx(circuit, physical_label, physical_target_label)
                circuit = self._add_two_qubit_noise(
                    circuit, physical_label, physical_target_label
                )
            else:
                pass

        return circuit
