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


def make_topology_with_meas_error():
    # Initial values mimic a topology generated from an older calibration
    # (readout_assignment_error is n/4096, as reported).
    return {
        "device_id": "test-device",
        "qubits": [
            {
                "id": 0,
                "physical_id": 17,
                "meas_error": {
                    "prob_meas1_prep0": 0.01,
                    "prob_meas0_prep1": 0.02,
                    "readout_assignment_error": 468 / 4096,
                },
            },
            {
                "id": 1,
                "physical_id": 19,
                "meas_error": {
                    "prob_meas1_prep0": 0.03,
                    "prob_meas0_prep1": 0.04,
                    "readout_assignment_error": 670 / 4096,
                },
            },
        ],
        "couplings": [{"control": 1, "target": 0}],
        "calibrated_at": "2026-01-01T00:00:00Z",
    }


@pytest.fixture
def readout_backend(mocker, tmp_path):
    import json

    topology_path = tmp_path / "device_topology.json"
    topology_path.write_text(json.dumps(make_topology_with_meas_error()))
    experiment_class = mocker.patch("device_gateway.plugins.qubex.backend.Experiment")
    experiment = experiment_class.return_value
    experiment.get_qubit_label.side_effect = lambda index: f"Q{index:02}"
    fidelities = {
        "Q17": [1 - 0.0641, 1 - 0.1123],
        "Q19": [1 - 0.2783, 1 - 0.2732],
    }

    def build_classifier(targets, **kwargs):
        return {"readout_fidelities": {targets: fidelities[targets]}}

    experiment.build_classifier.side_effect = build_classifier
    backend = QubexBackend(
        "QPU", {"device_topology_json_path": str(topology_path)}, make_plugin_config()
    )
    return backend, topology_path


class TestQubexReadoutCalibration:
    def test_updates_all_meas_error_fields_consistently(self, readout_backend):
        import json

        backend, topology_path = readout_backend

        backend._readout_calibration()

        saved = json.loads(topology_path.read_text())
        for qubit in saved["qubits"]:
            meas_error = qubit["meas_error"]
            expected = (
                meas_error["prob_meas1_prep0"] + meas_error["prob_meas0_prep1"]
            ) / 2
            assert meas_error["readout_assignment_error"] == pytest.approx(expected)
        q17 = saved["qubits"][0]["meas_error"]
        assert q17["prob_meas1_prep0"] == pytest.approx(0.0641)
        assert q17["prob_meas0_prep1"] == pytest.approx(0.1123)
        assert q17["readout_assignment_error"] == pytest.approx(0.0882)
        q19 = saved["qubits"][1]["meas_error"]
        assert q19["prob_meas1_prep0"] == pytest.approx(0.2783)
        assert q19["prob_meas0_prep1"] == pytest.approx(0.2732)
        assert q19["readout_assignment_error"] == pytest.approx(0.27575)
        # Other fields are preserved.
        assert saved["calibrated_at"] == "2026-01-01T00:00:00Z"
        assert saved["couplings"] == [{"control": 1, "target": 0}]

    def test_does_not_overwrite_newer_topology_with_stale_cache(self, readout_backend):
        import json

        backend, topology_path = readout_backend
        _ = backend.device_topology  # populate the cache
        newer = make_topology_with_meas_error()
        newer["calibrated_at"] = "2026-02-01T00:00:00Z"
        topology_path.write_text(json.dumps(newer))

        backend._readout_calibration()

        saved = json.loads(topology_path.read_text())
        assert saved["calibrated_at"] == "2026-02-01T00:00:00Z"

    def test_warns_when_assignment_error_is_worse_than_random(
        self, readout_backend, caplog
    ):
        import logging

        backend, _ = readout_backend
        readout_errors = {
            "Q17": {
                "prob_meas1_prep0": 0.4973,
                "prob_meas0_prep1": 0.9447,
                "readout_assignment_error": 0.721,
            }
        }

        with caplog.at_level(logging.WARNING):
            backend._update_device_topology_readout_errors(readout_errors)

        assert "not better than random guessing" in caplog.text
        assert (
            backend.device_topology["qubits"][0]["meas_error"] == readout_errors["Q17"]
        )
