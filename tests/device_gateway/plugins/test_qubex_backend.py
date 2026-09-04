from unittest.mock import MagicMock

import pytest

pytest.importorskip("qubex.experiment")

from device_gateway.plugins.qubex.backend import QubexBackend


def make_topology():
    return {
        "qubits": [{"id": 0, "physical_id": 0}],
        "couplings": [],
    }


def make_plugin_config():
    return {
        "chip_id": "test-chip",
        "config_dir": "/config/{chip_id}",
        "params_dir": "/params/{chip_id}",
        "calib_note_path": "/calibration/{chip_id}/calib_note.json",
        "configuration_mode": "ge-ef-cr",
        "shot_interval": 123456,
    }


class TestQubexBackend:
    def test_passes_new_settings_to_qubex(self, mocker):
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=make_topology(),
        )
        experiment = mocker.patch("device_gateway.plugins.qubex.backend.Experiment")

        QubexBackend("QPU", {}, make_plugin_config())

        experiment.assert_called_once_with(
            chip_id="test-chip",
            qubits=[0],
            config_dir="/config/test-chip",
            params_dir="/params/test-chip",
            calib_note_path="/calibration/test-chip/calib_note.json",
            configuration_mode="ge-ef-cr",
        )

    def test_execute_uses_n_shots_and_configured_shot_interval(self, mocker):
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=make_topology(),
        )
        experiment_class = mocker.patch(
            "device_gateway.plugins.qubex.backend.Experiment"
        )
        experiment = experiment_class.return_value
        experiment.measure.return_value.get_counts.return_value = {"0": 10}
        backend = QubexBackend("QPU", {}, make_plugin_config())
        schedule = MagicMock()

        counts = backend._execute(schedule, shots=10)

        assert counts == {"0": 10}
        experiment.measure.assert_called_once_with(
            schedule,
            mode="single",
            n_shots=10,
            shot_interval=123456,
            reset_awg_and_capunits=True,
        )
        experiment.measure.return_value.get_counts.assert_called_once_with(targets=[])
