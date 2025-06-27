import logging
import os

import numpy as np
from qiskit.qasm3 import loads
from qiskit.result import Counts, LocalReadoutMitigator, ProbDistribution
from qubex.experiment import Experiment
from qubex.measurement.measurement import DEFAULT_INTERVAL, DEFAULT_SHOTS
from qubex.pulse import PulseSchedule
from qubex.version import get_package_version

from device_gateway.core.base_backend import SUCCESS_MESSAGE, BaseBackend
from device_gateway.plugins.qubex.circuit import QubexCircuit

logger = logging.getLogger("device_gateway")

available_qubits = [
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    10,
    11,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    32,
    33,
    34,
    35,
    37,
    38,
    48,
    49,
    50,
    52,
    53,
    54,
    57,
]


class QubexBackend(BaseBackend):
    def __init__(self, config: dict):
        super().__init__(config)
        logger.info(f"Qubex version: {get_package_version('qubex')}")
        self._execute_readout_calibration = True
        self._experiment = Experiment(
            chip_id=os.getenv("CHIP_ID", "64Q"),
            qubits=self.qubits,
            config_dir=os.getenv("CONFIG_DIR", "/app/qubex_config"),
            params_dir=os.getenv("PARAMS_DIR", "/app/qubex_config"),
            calib_note_path=os.getenv(
                "CALIB_NOTE_PATH", "/app/qubex_config/calib_note.json"
            ),
        )
        logger.info(f"Qubex version: {get_package_version('qubex')}")

    def _search_qubit_by_id(self, id):
        for qubit in self.device_topology.get("qubits", []):
            if qubit.get("id") == id:
                return qubit
        return None

    def _build_classifier(self):
        """
        Build the classifier for a given qubit.
        This method is called during the initialization of the QubexBackend.
        """
        note = {}
        # for qubit in self.qubits:
        for qubit in available_qubits:
            qubit = f"Q{qubit:02d}"  # Format qubit as Q01, Q02, etc.
            logger.info(f"Building classifier for qubit {qubit}")
            try:
                res = self._experiment.build_classifier(targets=qubit, plot=False)
                note[qubit] = {
                    "p0m1": 1 - res["readout_fidelties"][qubit][0],
                    "p1m0": 1 - res["readout_fidelties"][qubit][1],
                }
                logger.info(f"Classifier built for qubit {qubit}: {note[qubit]}")
            except Exception as e:
                logger.error(f"Failed to build classifier for qubit {qubit}: {e}")
                note[qubit] = {"p0m1": 0.0, "p1m0": 0.0}
        return note

    def _readout_calibration(self):
        """
        Perform readout calibration for the qubits.
        This method is called during the initialization of the QubexBackend.
        """
        readout_errors = self._build_classifier()
        self._update_device_topology_readout_errors(readout_errors)

    def _update_device_topology_readout_errors(self, readout_errors):
        """
        Update the device topology with readout errors.
        This method is called during the initialization of the QubexBackend.
        """
        device_topology = self.device_topology
        # for qubit in self.qubits:
        for qubit in available_qubits:
            qubit = f"Q{qubit:02d}"  # Format qubit as Q01, Q02, etc.
            id = self.physical_index(qubit)
            qubit_info = self._search_qubit_by_id(id)
            if qubit_info is not None:
                qubit_info["meas_error"]["prob_meas1_prep0"] = readout_errors[qubit][
                    "p0m1"
                ]
                qubit_info["meas_error"]["prob_meas0_prep1"] = readout_errors[qubit][
                    "p1m0"
                ]
            logger.info(
                f"Updated readout errors for qubit {qubit}: {qubit_info['meas_error']}"
            )
            device_topology["qubits"][id] = qubit_info
        self.save_device_topology(device_topology)

    def _get_circuit(self) -> QubexCircuit:
        return QubexCircuit(self)

    def _execute(self, circuit: PulseSchedule, shots: int = DEFAULT_SHOTS):
        """
        Execute the compiled circuit for a specified number of shots.
        The compiled_circuit is produced by the PulseSchedule class.
        """
        logger.info(f"Executing quantum circuit with {shots} shots")
        return self._experiment.measure(
            circuit,
            mode="single",
            shots=shots,
            interval=DEFAULT_INTERVAL,
        )

    def _save_memory(self, memory: list[str], filename: str):
        """
        Save the memory to a file.
        This method is called after executing the quantum circuit.
        """
        with open(filename, "w") as f:
            for item in memory:
                f.write(f"{item}\n")

    def execute(self, job_id: str, program: str, shots: int = 1024) -> tuple[dict, str]:
        """Execute the compiled circuit for a specified number of shots.
        The compiled_circuit is produced by the PulseSchedule class.
        """
        if self.is_active() and self._execute_readout_calibration:
            logger.info("Performing readout calibration")
            self._readout_calibration()
            self._execute_readout_calibration = False
        qc = loads(program)
        circuit = self._get_circuit()
        compiled_circuit = circuit.compile(qc)
        result = self._execute(compiled_circuit, shots=shots)
        counts = result.get_counts(targets=self.classical_registers)
        counts = self._remove_zero_values(counts)
        logger.info(f"counts={counts}")
        memory = result.get_memory(targets=self.classical_registers)
        logger.info(f"memory={memory}")
        if memory:
            if not os.path.exists("memories"):
                os.makedirs("memories")
            logger.info(f"Saving memory to /app/memories/{job_id}.txt")
            self._save_memory(memory, f"/app/memories/{job_id}.txt")

        return counts, SUCCESS_MESSAGE

    def qubex_error_mitigation(
        self,
        counts,
        shots,
        measured_qubits,
    ) -> dict[str, int]:
        """
        Mitigate the measurement result.
        """
        physical_qubits = []
        for qubit in measured_qubits:
            physical_qubits.append(self.physical_label(qubit))
        total = sum(counts.values())
        probabilities = {key: count / total for key, count in counts.items()}
        labels = [f"{i}" for i in probabilities.keys()]
        prob = np.array(list(probabilities.values()))
        cm_inv = self._experiment.get_inverse_confusion_matrix(
            targets=self.classical_registers
        )
        mitigated_prob = prob @ cm_inv
        prob_dict = dict(zip(labels, mitigated_prob))
        mitigated_counts = {k: int(v * shots) for k, v in prob_dict.items()}
        return mitigated_counts

    def qiskit_error_mitigation(
        self,
        counts,
        shots,
        measured_qubits,
    ) -> dict[str, int]:
        assignment_matrices = []
        qubits = self.device_topology["qubits"]
        n_qubits = len(measured_qubits)

        # LocalReadoutMitigator (used below) creates a vector of length 2^(#qubits).
        if n_qubits > 32:  # If #qubits is 32, it requires a memory of 32GB.
            # TODO rename pseudo_inverse to local_amat_inverse after the Web API schema is changed
            raise ValueError(
                "input measured_qubits is too large, it requires a memory of over 32GB"
            )

        for id in measured_qubits:
            mes_error = qubits[id]["meas_error"]
            amat = np.array(
                [
                    [1 - mes_error["prob_meas1_prep0"], mes_error["prob_meas0_prep1"]],
                    [mes_error["prob_meas1_prep0"], 1 - mes_error["prob_meas0_prep1"]],
                ],
                dtype=float,
            )
            assignment_matrices.append(amat)
        local_mitigator = LocalReadoutMitigator(assignment_matrices)
        bin_counts = {f"0b{k}": v for k, v in counts.items()}

        # TODO The Web API data type for count is unsigned int.
        # So after getting the nearest_prob, the count count is cast to an int. This reduces the accuracy.
        # As the data returned to the user, it should be selectable not only counts (int) but also quasi-distribution (float).
        # TODO estimation jobs should be calculated by LocalReadoutMitigator.expectation_value
        # It needs to specify memory_slots of Counts and num_bits of binary_probabilities(...) to prevent
        # the leading zeros in each bit string from being removed.
        quasi_dist = local_mitigator.quasi_probabilities(
            Counts(bin_counts, memory_slots=n_qubits)
        )
        logger.info(f"quasi_dist : {quasi_dist}")
        nearest_prob: ProbDistribution = quasi_dist.nearest_probability_distribution()  # type: ignore
        logger.info(f"nearest_prob : {nearest_prob}")
        bin_prob = nearest_prob.binary_probabilities(num_bits=n_qubits)
        logger.info(f"bin prob :{bin_prob}")
        mitigated_counts = {k: int(v * shots) for k, v in bin_prob.items()}
        return mitigated_counts
