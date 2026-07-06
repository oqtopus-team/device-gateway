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


def test_initialize_backend_uses_default_when_missing(mocker):
    """Test that _initialize_backend falls back to DEFAULT_BACKEND."""
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
    server = ServerImpl(config_no_default)
    assert server.backend_name == "qulacs"
