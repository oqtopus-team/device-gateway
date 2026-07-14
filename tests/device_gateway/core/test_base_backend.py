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


def make_plugin_config():
    return {"supported_gates": ["x", "sx", "rz", "cx", "measure", "barrier", "delay"]}


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


class TestSupportedGates:
    def test_supported_gates_is_a_set_when_configured(self, mocker):
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=make_topology(),
        )
        backend = QulacsBackend("simulator", make_config(), make_plugin_config())

        assert backend.supported_gates == {
            "x",
            "sx",
            "rz",
            "cx",
            "measure",
            "barrier",
            "delay",
        }

    def test_supported_gates_is_none_when_plugin_config_omitted(self, mocker):
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=make_topology(),
        )
        backend = QulacsBackend("simulator", make_config())

        assert backend.supported_gates is None

    def test_supported_gates_is_none_when_key_omitted_from_plugin_config(self, mocker):
        mocker.patch(
            "device_gateway.core.base_backend.BaseBackend.load_device_topology",
            return_value=make_topology(),
        )
        backend = QulacsBackend("simulator", make_config(), {})

        assert backend.supported_gates is None


class TestDeviceTopologyCaching:
    def _mock_topology_file(self, mocker, topology):
        mocker.patch("builtins.open", mocker.mock_open())
        return mocker.patch(
            "device_gateway.core.base_backend.json.load", return_value=topology
        )

    def _make_config_with_topology_path(self):
        config = make_config()
        config["device_topology_json_path"] = "config/device_topology_sim.json"
        return config

    def test_physical_map_reuses_cache_after_first_load(self, mocker):
        topology = {**make_topology(num_qubits=2), "couplings": []}
        mock_json_load = self._mock_topology_file(mocker, topology)
        backend = QulacsBackend("simulator", self._make_config_with_topology_path())

        backend.physical_map
        backend.physical_map
        backend.qubits

        assert mock_json_load.call_count == 1

    def test_load_device_topology_forces_a_fresh_read(self, mocker):
        topology = {**make_topology(num_qubits=2), "couplings": []}
        mock_json_load = self._mock_topology_file(mocker, topology)
        backend = QulacsBackend("simulator", self._make_config_with_topology_path())

        backend.physical_map  # populates the cache
        backend.load_device_topology()  # explicit call forces a fresh read

        assert mock_json_load.call_count == 2
