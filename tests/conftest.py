"""Global test configuration and fixtures for all tests."""

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_fixtures_dir() -> Path:
    """Get the path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def qubex_fixtures_dir(test_fixtures_dir) -> Path:
    """Get the path to qubex test fixtures."""
    return test_fixtures_dir / "qubex"


@pytest.fixture
def qubex_config_dir(qubex_fixtures_dir) -> str:
    """Get qubex config directory as absolute path string."""
    return str((qubex_fixtures_dir / "qubex_config").resolve())


@pytest.fixture
def qubex_test_env(qubex_fixtures_dir):
    """Set up test environment variables for qubex."""
    config_dir = str((qubex_fixtures_dir / "qubex_config").resolve())
    test_env = {
        "CHIP_ID": "TEST_CHIP",
        "CONFIG_DIR": config_dir,
        "PARAMS_DIR": config_dir,
        "CALIB_NOTE_PATH": str(
            (qubex_fixtures_dir / "qubex_config" / "calib_note.json").resolve()
        ),
    }

    # Save original environment
    original_env = {}
    for key in test_env:
        original_env[key] = os.environ.get(key)

    # Set test environment
    for key, value in test_env.items():
        os.environ[key] = value

    yield test_env

    # Restore original environment
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture
def sample_qubex_config(qubex_fixtures_dir):
    """Sample configuration for QubexBackend tests."""
    return {
        "backend_name": "qubex",
        "device": {
            "qubits": [0, 1, 2],
            "couplings": [[0, 1], [1, 2]],
        },
        "device_topology_json_path": str(qubex_fixtures_dir / "device_topology.json"),
        "n_shots": 1000,
    }
