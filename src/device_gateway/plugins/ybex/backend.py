import json
import logging
import shlex
import subprocess
from collections import Counter

from qiskit.qasm3 import loads

from device_gateway.core.base_backend import SUCCESS_MESSAGE, BaseBackend
from device_gateway.plugins.ybex.circuit import YbexCircuit
from device_gateway.plugins.ybex.compiler import YbexCompiler

logger = logging.getLogger("device_gateway")


class YbexBackend(BaseBackend):
    def __init__(self, config: dict):
        super().__init__(config)

        # Get the external command template from config
        command_template = config.get("plugin", {}).get("backend", {}).get("command")
        logger.debug(f"{command_template=}")

        # # Raise error if command is not defined in the config
        if not command_template:
            msg = "Config key 'plugin.backend.command' is missing."
            logger.error(msg)
            raise ValueError(msg)

        self._command_template = command_template
        self._compiler = YbexCompiler(self)

    # TODO remove this method
    def _get_circuit(self) -> YbexCircuit:
        return YbexCircuit(self)

    def _execute(self, circuit: YbexCircuit, shots: int = 1024) -> dict[str, int]:
        """
        Execute the compiled circuit for a specified number of shots.
        The circuit is produced by the Circuit class.
        """
        # Format the command string with actual parameters
        command = self._command_template.format(shots=shots, angle=circuit._angle)
        logger.debug(f"Executing command: {command}")
        try:
            # Run the external command safely using shlex.split
            result_str = subprocess.run(
                shlex.split(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            ).stdout
            logger.debug(f"Command executed successfully. result={result_str}")

        except subprocess.CalledProcessError as e:
            msg = "Execution of external command failed."
            logger.error(msg)
            raise RuntimeError(msg) from e

        # Parse the JSON output
        result = json.loads(result_str)
        return Counter(result)

    def _remap_counts(
        self, full_counts: dict[str, int], measure_map: dict[int, int], bit_count: int
    ) -> dict[str, int]:
        """Remap the output bitstrings according to the classical bit mapping.

        Args:
            full_counts: Full counts from the execution
            measure_map: Mapping of classical bits to qubits
            bit_count: Total number of classical bits

        Returns:
            A dictionary with remapped bitstrings as keys and their counts as values.

        """
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
        """Execute the quantum program using the Ybex backend.

        Args:
            program: The quantum program in OpenQASM3 format
            shots: Number of shots to execute
        Returns:
            A tuple containing the counts of measurement outcomes and a success message.

        """
        qc = loads(program)
        circuit = self._compiler.compile(qc)
        counts = self._execute(circuit, shots=shots)
        counts = self._remove_zero_values(counts)

        # Build a classical-bit-to-qubit mapping for measurement instructions
        measure_map = {}
        for instruction in qc.data:
            if instruction.name == "measure":
                qubit_index = qc.find_bit(instruction.qubits[0])[0]
                clbit_index = qc.find_bit(instruction.clbits[0])[0]
                measure_map[clbit_index] = qubit_index

        # Reorder output counts according to classical register layout
        bit_count = len(qc.clbits)
        counts = self._remap_counts(counts, measure_map, bit_count)
        logger.info(f"counts={counts}")

        return counts, SUCCESS_MESSAGE
