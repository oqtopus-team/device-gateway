import logging
from collections import Counter

from qiskit.qasm3 import loads
from qulacs import QuantumCircuit as QulacsQuantumCircuit
from qulacs import QuantumState

from device_gateway.core.base_backend import SUCCESS_MESSAGE, BaseBackend
from device_gateway.plugins.qulacs.circuit import QulacsCircuit

logger = logging.getLogger("device_gateway")


class QulacsBackend(BaseBackend):
    def __init__(self, config: dict):
        super().__init__(config)

    def _get_circuit(self) -> QulacsCircuit:
        return QulacsCircuit(self)

    def _execute(self, circuit: QulacsQuantumCircuit, shots: int = 1024) -> dict:
        """
        Execute the compiled circuit for a specified number of shots.
        The circuit is produced by the Circuit class.
        """
        logger.info(f"Executing quantum circuit with {shots} shots")
        state = QuantumState(circuit.get_qubit_count())
        circuit.update_quantum_state(state)
        result = Counter(state.sampling(shots))
        counts = {}
        for key, value in result.items():
            counts[format(key, "0" + str(circuit.get_qubit_count()) + "b")] = value
        logger.info(f"Execution complete, counts: {counts}")
        return counts

    def _remap_counts(
        self, full_counts: dict[str, int], measure_map: dict[int, int], bit_count: int
    ) -> dict[str, int]:
        result = Counter()

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
        logger.debug(f"measure_map={measure_map}")

        bit_count = len(qc.clbits)
        counts = self._remap_counts(counts, measure_map, bit_count)
        logger.info(f"counts={counts}")

        return counts, SUCCESS_MESSAGE
