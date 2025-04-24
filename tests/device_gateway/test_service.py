from unittest.mock import MagicMock

import pytest

from device_gateway.core.plugin_manager import (
    BackendPluginManager,
    CircuitPluginManager,
)
from device_gateway.service import ServerImpl


@pytest.fixture
def mock_backend_manager():
    manager = MagicMock(spec=BackendPluginManager)
    return manager


@pytest.fixture
def mock_circuit_manager():
    manager = MagicMock(spec=CircuitPluginManager)
    return manager


@pytest.fixture
def config():
    return {"backend": "qulacs"}


def test_server_init_with_default_managers(config):
    """Test server initialization with default managers."""
    server = ServerImpl(config)
    assert isinstance(server._backend_manager, BackendPluginManager)
    assert isinstance(server._circuit_manager, CircuitPluginManager)


def test_server_init_with_custom_managers(
    config, mock_backend_manager, mock_circuit_manager
):
    """Test server initialization with custom managers."""
    server = ServerImpl(
        config,
        backend_manager=mock_backend_manager,
        circuit_manager=mock_circuit_manager,
    )
    assert server._backend_manager == mock_backend_manager
    assert server._circuit_manager == mock_circuit_manager


def test_load_plugin_with_unsupported_backend(
    config, mock_backend_manager, mock_circuit_manager
):
    """Test loading unsupported backend plugin."""
    server = ServerImpl(
        config,
        backend_manager=mock_backend_manager,
        circuit_manager=mock_circuit_manager,
    )
    with pytest.raises(ImportError):
        server._load_plugin("unsupported_backend")


def test_load_plugin_with_import_error(
    config, mock_backend_manager, mock_circuit_manager
):
    """Test handling of import error during plugin loading."""
    mock_backend_manager.load_backend.side_effect = ImportError("Test error")
    server = ServerImpl(
        config,
        backend_manager=mock_backend_manager,
        circuit_manager=mock_circuit_manager,
    )
    with pytest.raises(ImportError):
        server._load_plugin("qulacs")
