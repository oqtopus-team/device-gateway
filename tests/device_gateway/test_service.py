import json
from unittest.mock import MagicMock

import pytest

from device_gateway.service import ServerImpl


@pytest.fixture
def config():
    return {
        "default_backend": "qulacs",
        "backend_di_container": {
            "registry": {
                "qulacs": {
                    "_target_": "device_gateway.plugins.qulacs.backend.QulacsBackend",
                    "device_type": "simulator",
                    "config": {
                        "device_info": {
                            "provider_id": "oqtopus",
                            "max_shots": 10000,
                        },
                        "device_status_path": "config/device_status",
                        "device_topology_json_path": "config/device_topology_sim.json",
                    },
                }
            }
        },
    }


@pytest.fixture
def server(mocker, config):
    def _fake_initialize(self, config):
        self.backend_name = "qulacs"
        self.backend = MagicMock()

    mocker.patch.object(ServerImpl, "_initialize_backend", _fake_initialize)
    return ServerImpl(config)


def test_server_init(server):
    """Test server initialization."""
    assert server.backend_name == "qulacs"
    assert server.backend is not None


def test_initialize_backend_sets_backend_name(mocker, config):
    """Test that _initialize_backend sets backend_name from config."""
    mocker.patch(
        "device_gateway.service.DiContainer.get",
        return_value=MagicMock(),
    )
    server = ServerImpl(config)
    assert server.backend_name == "qulacs"


def test_get_device_info_parameters_uses_fresh_topology(server):
    """GetDeviceInfo must force a fresh disk read instead of the cached property,
    so it reports the latest calibration data."""
    fresh_topology = {
        "qubits": [{"id": 0, "physical_id": 0}],
        "calibrated_at": "2026-01-01T00:00:00Z",
    }
    server.backend.load_device_topology.return_value = fresh_topology
    server.backend.device_info = {"device_id": "d1", "max_qubits": 1}

    parameters = server._get_device_info_parameters()

    server.backend.load_device_topology.assert_called_once()
    assert parameters["calibrated_at"] == "2026-01-01T00:00:00Z"
    assert json.loads(parameters["device_info"]) == fresh_topology


def test_initialize_backend_raises_when_default_backend_missing(mocker):
    """Test that _initialize_backend requires default_backend in config."""
    config_no_default = {
        "backend_di_container": {
            "registry": {
                "qulacs": {
                    "_target_": "device_gateway.plugins.qulacs.backend.QulacsBackend",
                    "device_type": "simulator",
                    "config": {},
                }
            }
        }
    }
    mocker.patch(
        "device_gateway.service.DiContainer.get",
        return_value=MagicMock(),
    )
    with pytest.raises(KeyError):
        ServerImpl(config_no_default)
