import logging
from collections import Counter

from qiskit.qasm3 import loads
from qulacs import QuantumCircuit as QulacsQuantumCircuit
from qulacs import NoiseSimulator
from qulacs import QuantumState

from device_gateway.core.base_backend import SUCCESS_MESSAGE, BaseBackend
from device_gateway.plugins.qulacs.circuit import QulacsCircuit

logger = logging.getLogger("device_gateway")


class QulacsBackend(BaseBackend):
    def __init__(self, config: dict):
        super().__init__(config)

    def _get_circuit(self) -> QulacsCircuit:
        return QulacsCircuit(self)

    def _noise_enabled(self) -> bool:
        plugin_config = self.config.get("plugin", {})
        noise_model = plugin_config.get("noise_model", {})
        return bool(noise_model.get("enabled", False))

    def _noise_model_config(self) -> dict:
        plugin_config = self.config.get("plugin", {})
        return plugin_config.get("noise_model", {})

    def _readout_error_enabled(self) -> bool:
        return bool(self._noise_enabled() and self._noise_model_config().get("readout_error", True))

    def _validate_probability(self, prob: float, name: str) -> float:
        if not (0.0 <= prob <= 1.0):
            raise ValueError(f"{name} must be in [0, 1], got {prob}")
        return prob

    def _build_readout_error_map(self, measure_map: dict[int, int]) -> dict[int, tuple[float, float]]:
        qubits = self.device_topology.get("qubits", [])
        qubit_error_map = {
            qubit.get("id"): qubit.get("meas_error", {}) for qubit in qubits
        }
        readout_error_map: dict[int, tuple[float, float]] = {}
        for clbit_index, qubit_index in measure_map.items():
            meas_error = qubit_error_map.get(qubit_index, {})
            p10 = self._validate_probability(
                float(meas_error.get("prob_meas1_prep0", 0.0)),
                f"prob_meas1_prep0 for qubit {qubit_index}",
            )
            p01 = self._validate_probability(
                float(meas_error.get("prob_meas0_prep1", 0.0)),
                f"prob_meas0_prep1 for qubit {qubit_index}",
            )
            readout_error_map[clbit_index] = (p10, p01)
        return readout_error_map

    def _round_distribution(self, dist: dict[int, float], shots: int) -> dict[int, int]:
        floored = {state: int(value) for state, value in dist.items() if value > 0}
        remainder = shots - sum(floored.values())
        if remainder <= 0:
            return floored

        fractions = sorted(
            (
                (state, dist[state] - floored.get(state, 0))
                for state in dist
                if dist[state] > 0
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        for state, _ in fractions[:remainder]:
            floored[state] = floored.get(state, 0) + 1
        return floored

    def _apply_readout_error(
        self,
        counts: dict[str, int],
        measure_map: dict[int, int],
        bit_count: int,
    ) -> dict[str, int]:
        if not self._readout_error_enabled():
            return counts

        readout_error_map = self._build_readout_error_map(measure_map)
        if not readout_error_map:
            return counts

        total_shots = sum(counts.values())
        dist: dict[int, float] = {int(bitstring, 2): float(count) for bitstring, count in counts.items()}

        for clbit_index in range(bit_count):
            p10, p01 = readout_error_map.get(clbit_index, (0.0, 0.0))
            if p10 == 0.0 and p01 == 0.0:
                continue

            mask = 1 << clbit_index
            updated_dist: dict[int, float] = {}
            for state, weight in dist.items():
                if state & mask:
                    state_keep = state
                    state_flip = state & ~mask
                    updated_dist[state_keep] = updated_dist.get(state_keep, 0.0) + weight * (1.0 - p01)
                    updated_dist[state_flip] = updated_dist.get(state_flip, 0.0) + weight * p01
                else:
                    state_keep = state
                    state_flip = state | mask
                    updated_dist[state_keep] = updated_dist.get(state_keep, 0.0) + weight * (1.0 - p10)
                    updated_dist[state_flip] = updated_dist.get(state_flip, 0.0) + weight * p10
            dist = updated_dist

        rounded_dist = self._round_distribution(dist, total_shots)
        remapped_counts = {}
        for state, count in rounded_dist.items():
            if count <= 0:
                continue
            remapped_counts[format(state, f"0{bit_count}b")] = count
        return remapped_counts

    def _execute(self, circuit: QulacsQuantumCircuit, shots: int = 1024) -> dict:
        """
        Execute the compiled circuit for a specified number of shots.
        The circuit is produced by the Circuit class.
        """
        state = QuantumState(circuit.get_qubit_count())
        if self._noise_enabled():
            simulator = NoiseSimulator(circuit, state)
            result = Counter(simulator.execute(shots))
        else:
            circuit.update_quantum_state(state)
            result = Counter(state.sampling(shots))
        counts = {}
        for key, value in result.items():
            counts[format(key, "0" + str(circuit.get_qubit_count()) + "b")] = value
        return counts

    def _remap_counts(
        self, full_counts: dict[str, int], measure_map: dict[int, int], bit_count: int
    ) -> dict[str, int]:
        result: Counter[str] = Counter()

        for bitstring, count in full_counts.items():
            # reverse the bitstring so bit index 0 is at the rightmost position
            reversed_bitstring = bitstring[::-1]
            new_bits = []
            for clbit_index in range(bit_count):
                if clbit_index in measure_map:
                    # get the corresponding qubit index and extract the measured bit
                    qubit_index = measure_map[clbit_index]
                    bit = reversed_bitstring[qubit_index]
                else:
                    # if the classical bit was not assigned, set to 0
                    bit = "0"
                new_bits.append(bit)

            # reverse the bitstring again to move bit index 0 to the rightmost position
            new_key = "".join(new_bits)[::-1]

            result[new_key] += count

        return dict(result)

    def execute(self, program: str, shots: int = 1024) -> tuple[dict, str]:
        qc = loads(program)
        circuit = self._get_circuit()
        compiled_circuit = circuit.compile(qc)
        counts = self._execute(compiled_circuit, shots=shots)
        counts = self._remove_zero_values(counts)

        measure_map = {}
        for instruction in qc.data:
            if instruction.name == "measure":
                qubit_index = qc.find_bit(instruction.qubits[0])[0]
                clbit_index = qc.find_bit(instruction.clbits[0])[0]
                measure_map[clbit_index] = qubit_index

        bit_count = len(qc.clbits)
        counts = self._remap_counts(counts, measure_map, bit_count)
        counts = self._apply_readout_error(counts, measure_map, bit_count)
        counts = self._remove_zero_values(counts)
        logger.info(f"counts={counts}")

        return counts, SUCCESS_MESSAGE
