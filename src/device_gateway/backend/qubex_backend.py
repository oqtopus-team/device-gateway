import logging

from qubex.experiment import Experiment
from qubex.measurement.measurement import DEFAULT_INTERVAL, DEFAULT_SHOTS
from qubex.pulse import PulseSchedule

from device_gateway.backend.base_backend import BaseBackend

logger = logging.getLogger("device_gateway")


class QubexBackend(BaseBackend):
    def __init__(self, virtual_physical_map: dict):
        super().__init__(virtual_physical_map)
        self._experiment = Experiment(
            chip_id="64Q",
            qubits=self.qubits,
            config_dir="/app/qubex_config",
            params_dir="/app/qubex_config",
            calib_note_path="/app/qubex_config/calib_note.json",
        )
        logger.info("Execute readout calibration...")
        self._experiment.build_classifier(plot=False)
        logger.info("Readout calibration complete")

    def execute(self, circuit: PulseSchedule, shots: int = DEFAULT_SHOTS) -> dict:
        """
        Execute the compiled circuit for a specified number of shots.
        The compiled_circuit is produced by the Circuit class.
        """
        logger.info(f"Executing quantum circuit with {shots} shots")
        initial_states = {qubit: "0" for qubit in self.qubits}
        return self._experiment.measure(
            circuit,
            initial_states=initial_states,
            mode="single",
            shots=shots,
            interval=DEFAULT_INTERVAL,
        ).counts
