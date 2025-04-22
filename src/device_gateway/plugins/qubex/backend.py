import logging
import os

import numpy as np
from qiskit.result import Counts, LocalReadoutMitigator, ProbDistribution
from qubex.experiment import Experiment
from qubex.measurement.measurement import DEFAULT_INTERVAL, DEFAULT_SHOTS
from qubex.pulse import PulseSchedule

from device_gateway.core.base_backend import BaseBackend

logger = logging.getLogger("device_gateway")


class QubexBackend(BaseBackend):
    def __init__(self, config: dict):
        super().__init__(config)
        self._experiment = Experiment(
            chip_id=os.getenv("CHIP_ID", "64Q"),
            qubits=self.qubits,
            config_dir=os.getenv("CONFIG_DIR", "/app/qubex_config"),
            params_dir=os.getenv("PARAMS_DIR", "/app/qubex_config"),
            calib_note_path=os.getenv(
                "CALIB_NOTE_PATH", "/app/qubex_config/calib_note.json"
            ),
        )

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
        for qubit in self.qubits:
            res = self._experiment.build_classifier(targets=qubit, plot=False)
            note[qubit] = {
                "p0m1": 1 - res["readout_fidelties"][qubit][0],
                "p1m0": 1 - res["readout_fidelties"][qubit][1],
            }
        return note

    def readout_calibration(self):
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
        for qubit in self.qubits:
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

    def execute(self, circuit: PulseSchedule, shots: int = DEFAULT_SHOTS):
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
        ).get_counts()

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
        cm_inv = self._experiment.get_inverse_confusion_matrix(physical_qubits)
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
