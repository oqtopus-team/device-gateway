import logging
from collections import Counter

from opentelemetry import trace
from qiskit.qasm3 import loads

from device_gateway.core.base_backend import SUCCESS_MESSAGE, BaseBackend
from device_gateway.plugins.stim.compiler import StimCompiler

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


class StimBackend(BaseBackend):
    def __init__(
        self, device_type: str, config: dict, plugin_config: dict | None = None
    ):
        super().__init__(device_type, config, plugin_config)
        # stim only supports Clifford gates; non-Clifford instructions are
        # logged and ignored by the compiler. supported_gates is optional and
        # retained for documentation / config validation consistency with the
        # qulacs backend, but does not cause jobs to fail.
        self.supported_gates = (
            set(self.plugin_config["supported_gates"])
            if "supported_gates" in self.plugin_config
            else None
        )
        self._compiler = StimCompiler(self)

    def _measure_map(self, qc) -> dict[int, int]:
        """Build a mapping from classical bit index to measured logical qubit index.

        Mirrors the qulacs backend: each `measure` instruction records which
        logical qubit feeds which classical bit.
        """
        measure_map = {}
        for instruction in qc.data:
            if instruction.name == "measure":
                qubit_index = qc.find_bit(instruction.qubits[0])[0]
                clbit_index = qc.find_bit(instruction.clbits[0])[0]
                measure_map[clbit_index] = qubit_index
        return measure_map

    def _logical_to_physical(self, logical_index: int) -> int:
        """Map a logical qubit index to a physical index from the topology."""
        physical_label = self.physical_index_to_physical_label[logical_index]
        return self.physical_label_to_physical_index[physical_label]

    def execute(self, program: str, shots: int = 1024) -> tuple[dict, str]:
        qiskit_circuit = loads(program)

        with tracer.start_as_current_span("device_gateway.compile") as span:
            if span.is_recording():
                span.set_attribute(
                    "device_gateway.circuit.num_qubits", qiskit_circuit.num_qubits
                )
                span.set_attribute(
                    "device_gateway.circuit.num_clbits", qiskit_circuit.num_clbits
                )
                span.set_attribute(
                    "device_gateway.circuit.depth", qiskit_circuit.depth()
                )
            stim_circuit = self._compiler.compile(qiskit_circuit)

        with tracer.start_as_current_span("device_gateway._execute") as span:
            if span.is_recording():
                span.set_attribute("device_gateway.shots", shots)

            measure_map = self._measure_map(qiskit_circuit)
            bit_count = len(qiskit_circuit.clbits)

            # Append one M measurement per measured classical bit, in clbit
            # order, so the sampled column k maps directly to clbit
            # clbit_for_measurement[k]. Measurements are placed at the end
            # (end-of-circuit sampling), matching the qulacs backend semantics.
            clbit_for_measurement: list[int] = []
            for clbit in range(bit_count):
                if clbit in measure_map:
                    physical_index = self._logical_to_physical(measure_map[clbit])
                    stim_circuit.append("M", [physical_index])
                    clbit_for_measurement.append(clbit)

            if not clbit_for_measurement:
                # No measurement: all classical bits read 0, matching qulacs.
                counts = {"0" * bit_count: shots} if bit_count > 0 else {}
                counts = {k: v for k, v in counts.items() if v != 0}
                logger.info(f"counts={counts}")
                return counts, SUCCESS_MESSAGE

            samples = stim_circuit.compile_sampler().sample(shots)
            result: Counter[str] = Counter()
            for row in samples:
                bits = ["0"] * bit_count
                for k, clbit in enumerate(clbit_for_measurement):
                    bits[clbit] = "1" if row[k] else "0"
                # Reverse to match the qulacs backend's count-key ordering
                # ("".join(new_bits)[::-1]).
                result["".join(bits)[::-1]] += 1

        counts = {k: v for k, v in result.items() if v != 0}
        logger.info(f"counts={counts}")
        return counts, SUCCESS_MESSAGE
