from unittest.mock import MagicMock

import pytest

from device_gateway.core.plugin_manager import BackendPluginManager
from device_gateway.service import ServerImpl


@pytest.fixture
def mock_backend_manager():
    manager = MagicMock(spec=BackendPluginManager)
    return manager


@pytest.fixture
def config():
    return {"backend": "qulacs"}


@pytest.fixture
def server(mocker, config):
    def _fake_initialize(self, config):
        self.backend_name = "qulacs"
        self.backend = MagicMock()

    mocker.patch.object(ServerImpl, "_initialize_backend", _fake_initialize)
    return ServerImpl(config)


def test_server_init_with_default_managers(server):
    """Test server initialization with default managers."""
    assert isinstance(server._backend_manager, BackendPluginManager)


def test_load_plugin_with_unsupported_backend(server):
    """Test loading unsupported backend plugin."""
    with pytest.raises(ImportError):
        server._load_plugin({"name": "unsupported_backend"})


def test_load_plugin_with_import_error(server, mock_backend_manager):
    """Test handling of import error during plugin loading."""
    server._backend_manager = mock_backend_manager
    mock_backend_manager.load_backend.side_effect = ImportError("Test error")
    with pytest.raises(ImportError):
        server._load_plugin({"name": "qulacs"})
