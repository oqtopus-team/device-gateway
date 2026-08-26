import logging
from collections import Counter

from opentelemetry import trace
from qulacs import QuantumCircuit as QulacsQuantumCircuit
from qulacs import QuantumState

from device_gateway.core.base_backend import SUCCESS_MESSAGE, BaseBackend
from device_gateway.plugins.qulacs.compiler import QulacsCompiler

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class QulacsBackend(BaseBackend):
    def __init__(
        self, device_type: str, config: dict, plugin_config: dict | None = None
    ):
        super().__init__(device_type, config, plugin_config)
        # supported_gates is optional: when present, only those instruction names may
        # be compiled; when absent, QulacsCompiler performs no gate-name validation.
        self.supported_gates = (
            set(self.plugin_config["supported_gates"])
            if "supported_gates" in self.plugin_config
            else None
        )
        self._compiler = QulacsCompiler(self)

    def _execute(self, circuit: QulacsQuantumCircuit, shots: int = 1024) -> dict:
        """
        Execute the compiled circuit for a specified number of shots.
        The circuit is produced by the Circuit class.
        """
        state = QuantumState(circuit.get_qubit_count())
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
        qiskit_circuit = self._parse_program(program)
        with tracer.start_as_current_span("device_gateway.execute.compile"):
            qulacs_circuit = self._compiler.compile(qiskit_circuit)
        with tracer.start_as_current_span("device_gateway.execute.run") as span:
            span.set_attribute("device_gateway.shots", shots)
            counts = self._execute(qulacs_circuit, shots=shots)

        with tracer.start_as_current_span(
            "device_gateway.execute.post_process"
        ) as span:
            counts = {k: v for k, v in counts.items() if v != 0}

            measure_map = {}
            for instruction in qiskit_circuit.data:
                if instruction.name == "measure":
                    qubit_index = qiskit_circuit.find_bit(instruction.qubits[0])[0]
                    clbit_index = qiskit_circuit.find_bit(instruction.clbits[0])[0]
                    measure_map[clbit_index] = qubit_index

            bit_count = len(qiskit_circuit.clbits)
            counts = self._remap_counts(counts, measure_map, bit_count)
            span.set_attribute("device_gateway.result.num_outcomes", len(counts))
        logger.info(f"counts={counts}")

        return counts, SUCCESS_MESSAGE
