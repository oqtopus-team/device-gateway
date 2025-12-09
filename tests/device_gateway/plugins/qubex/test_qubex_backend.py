"""Basic unit tests for QubexBackend using AAA pattern."""

import pytest

from device_gateway.plugins.qubex.backend import QubexBackend
from device_gateway.plugins.qubex.circuit import QubexCircuit


@pytest.mark.usefixtures("qubex_test_env")
class TestQubexBackend:
    """Basic unit tests for QubexBackend using AAA pattern."""

    def test_init_creates_experiment_instance(self, sample_qubex_config):
        """Test QubexBackend initialization creates Experiment instance."""
        # Arrange & Act
        backend = QubexBackend(sample_qubex_config)

        # Assert
        assert backend._execute_readout_calibration is True
        assert hasattr(backend, "_experiment")

    def test_get_circuit_returns_qubex_circuit(self, sample_qubex_config):
        """Test _get_circuit method returns QubexCircuit instance."""
        # Arrange
        backend = QubexBackend(sample_qubex_config)

        # Act
        circuit = backend._get_circuit()

        # Assert
        assert isinstance(circuit, QubexCircuit)
        assert circuit._backend is backend
