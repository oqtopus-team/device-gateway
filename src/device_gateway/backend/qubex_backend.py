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
    def __init__(self, virtual_physical_map: dict):
        super().__init__(virtual_physical_map)
        self._experiment = Experiment(
            chip_id=CHIP_ID,
            qubits=self.qubits,
            config_dir=CONFGIG_DIR,
            params_dir=PARAMS_DIR,
            calib_note_path=CALIB_NOTE_PATH,
        )
        logger.info("Execute readout calibration...")
        for qubit in self.qubits:
            self._experiment.build_classifier(targets=qubit, plot=False)
        logger.info("Readout calibration complete")

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
