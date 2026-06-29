import pytest

from device_gateway.plugins.qulacs.backend import QulacsBackend


def make_config(device_id="from_config", max_qubits=7):
    return {
        "device_info": {
            "device_id": device_id,
            "max_qubits": max_qubits,
            "provider_id": "oqtopus",
            "max_shots": 1000,
        },
    }


def make_topology(device_id="from_topology", num_qubits=4):
    return {
        "device_id": device_id,
        "qubits": [{"id": i, "physical_id": i} for i in range(num_qubits)],
    }


class TestDeviceInfo:
    def test_uses_config_values_when_set(self, mocker):
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=make_topology(device_id="topology_id", num_qubits=4),
        )
        backend = QulacsBackend(
            "simulator", make_config(device_id="config_id", max_qubits=7)
        )

        info = backend.device_info

        assert info["device_id"] == "config_id"
        assert info["max_qubits"] == 7

    def test_uses_topology_device_id_when_config_device_id_is_none(self, mocker):
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=make_topology(device_id="topology_id"),
        )
        backend = QulacsBackend("simulator", make_config(device_id=None))

        info = backend.device_info

        assert info["device_id"] == "topology_id"

    def test_uses_topology_qubits_count_when_config_max_qubits_is_none(self, mocker):
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=make_topology(num_qubits=5),
        )
        backend = QulacsBackend("simulator", make_config(max_qubits=None))

        info = backend.device_info

        assert info["max_qubits"] == 5

    def test_raises_error_when_device_id_missing_from_both_config_and_topology(
        self, mocker
    ):
        topology = make_topology()
        del topology["device_id"]
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=topology,
        )
        backend = QulacsBackend("simulator", make_config(device_id=None))

        with pytest.raises(ValueError, match="device_id"):
            backend.device_info

    def test_raises_error_when_max_qubits_missing_from_both_config_and_topology(
        self, mocker
    ):
        topology = make_topology()
        del topology["qubits"]
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=topology,
        )
        backend = QulacsBackend("simulator", make_config(max_qubits=None))

        with pytest.raises(ValueError, match="max_qubits"):
            backend.device_info

    def test_does_not_mutate_config(self, mocker):
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=make_topology(device_id="topology_id", num_qubits=5),
        )
        backend = QulacsBackend(
            "simulator", make_config(device_id=None, max_qubits=None)
        )

        backend.device_info

        assert backend.config["device_info"]["device_id"] is None
        assert backend.config["device_info"]["max_qubits"] is None
