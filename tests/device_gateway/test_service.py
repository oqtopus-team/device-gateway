from unittest.mock import MagicMock, patch

import pytest

from device_gateway.core.plugin_manager import BackendPluginManager
from device_gateway.service import ServerImpl


@pytest.fixture
def mock_backend_manager():
    manager = MagicMock(spec=BackendPluginManager)
    return manager




@pytest.fixture
def config():
    return {
        "plugin": {"name": "qulacs"},
        "device_info": {
            "device_id": "test-qulacs",
            "provider_id": "test",
            "max_qubits": 3,
            "max_shots": 10000
        },
        "device_topology_json_path": "config/device_topology_sim.json",
        "device_status_path": "config/device_status"
    }


def test_server_init_with_default_managers(config):
    """Test server initialization with default managers."""
    server = ServerImpl(config)
    assert isinstance(server._backend_manager, BackendPluginManager)


def test_server_init_with_custom_managers(config, mock_backend_manager):
    """Test server initialization with custom managers."""
    # Note: ServerImpl currently only supports dependency injection during testing
    # by modifying the _backend_manager after initialization
    server = ServerImpl(config)
    server._backend_manager = mock_backend_manager
    assert server._backend_manager == mock_backend_manager


def test_load_plugin_with_unsupported_backend(config):
    """Test loading unsupported backend plugin."""
    server = ServerImpl(config)
    with pytest.raises(ImportError):
        server._load_plugin({"name": "unsupported_backend"})


def test_load_plugin_with_import_error(config, mock_backend_manager):
    """Test handling of import error during plugin loading."""
    mock_backend_manager.load_backend.side_effect = ImportError("Test error")
    server = ServerImpl(config)
    server._backend_manager = mock_backend_manager
    with pytest.raises(ImportError):
        server._load_plugin({"name": "qulacs"})
