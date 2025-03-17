import logging
from collections import Counter

from qulacs import QuantumCircuit as QulacsQuantumCircuit
from qulacs import QuantumState

from device_gateway.backend.base_backend import BaseBackend

logger = logging.getLogger("device_gateway")


class QulacsBackend(BaseBackend):
    def __init__(self, virtual_physical_map: dict):
        super().__init__(virtual_physical_map)

    def execute(self, circuit: QulacsQuantumCircuit, shots: int = 1024) -> dict:
        """
        Execute the compiled circuit for a specified number of shots.
        The compiled_circuit is produced by the Circuit class.
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
