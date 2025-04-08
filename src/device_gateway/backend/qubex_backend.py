import logging
import os

import numpy as np
from qubex.experiment import Experiment
from qubex.measurement.measurement import DEFAULT_INTERVAL, DEFAULT_SHOTS, MeasureResult
from qubex.pulse import PulseSchedule

from device_gateway.backend.base_backend import BaseBackend

logger = logging.getLogger("device_gateway")

CHIP_ID = os.getenv("CHIP_ID", "64Q")
CONFGIG_DIR = os.getenv("CONFIG_DIR", "/app/qubex_config")
PARAMS_DIR = os.getenv("PARAMS_DIR", "/app/qubex_config")
CALIB_NOTE_PATH = os.getenv("CALIB_NOTE_PATH", "/app/qubex_config/calib_note.json")


class QubexBackend(BaseBackend):
    def __init__(self, virtual_physical_map: dict, device_topology=None):
        super().__init__(virtual_physical_map)
        if device_topology is not None:
            self._device_topology = device_topology
        self._experiment = Experiment(
            chip_id=CHIP_ID,
            qubits=self.qubits,
            config_dir=CONFGIG_DIR,
            params_dir=PARAMS_DIR,
            calib_note_path=CALIB_NOTE_PATH,
        )
        logger.info("Execute readout calibration...")
        readout_errors = self._build_classifier()
        self._update_device_topology_readout_errors(readout_errors)
        logger.info("Readout calibration is done")

    def _search_qubit_by_id(self, id):
        for qubit in self._device_topology.get("qubits", []):
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

    def _update_device_topology_readout_errors(self, readout_errors):
        """
        Update the device topology with readout errors.
        This method is called during the initialization of the QubexBackend.
        """
        for qubit in self.qubits:
            id = self.virtual_qubit(qubit)
            qubit_info = self._search_qubit_by_id(id)
            if qubit_info is not None:
                qubit_info["meas_error"]["prob_meas1_prep0"] = readout_errors[qubit][
                    "p0m1"
                ]
                qubit_info["meas_error"]["prob_meas0_prep1"] = readout_errors[qubit][
                    "p1m0"
                ]
        return self._device_topology

    def execute(self, circuit: PulseSchedule, shots: int = DEFAULT_SHOTS):
        """
        Execute the compiled circuit for a specified number of shots.
        The compiled_circuit is produced by the Circuit class.
        """
        logger.info(f"Executing quantum circuit with {shots} shots")

        return self._experiment.measure(
            circuit,
            mode="single",
            shots=shots,
            interval=DEFAULT_INTERVAL,
        )

    def mitigate(
        self, measurement_result: MeasureResult, shots: int = DEFAULT_SHOTS
    ) -> dict[str, int]:
        """
        Mitigate the measurement result.
        """
        physical_qubits = self._used_physical_qubits
        probabilities = measurement_result.get_probabilities(physical_qubits)
        labels = [f"{i}" for i in probabilities.keys()]
        prob = np.array(list(probabilities.values()))
        cm_inv = self._experiment.get_inverse_confusion_matrix(physical_qubits)
        mitigated_prob = prob @ cm_inv
        prob_dict = dict(zip(labels, mitigated_prob))
        mitigated_counts = {k: int(v * shots) for k, v in prob_dict.items()}
        return mitigated_counts
