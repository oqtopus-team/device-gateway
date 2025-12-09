"""Basic unit tests for QubexCircuit using AAA pattern."""

import pytest
from qiskit import QuantumCircuit
from qubex.pulse import PulseSchedule

from device_gateway.plugins.qubex.backend import QubexBackend
from device_gateway.plugins.qubex.circuit import QubexCircuit


@pytest.mark.usefixtures("qubex_test_env")
class TestQubexCircuit:
    """Basic unit tests for QubexCircuit using AAA pattern."""

    def test_init_sets_backend(self, sample_qubex_config):
        """Test QubexCircuit initialization sets backend reference."""
        # Arrange
        backend = QubexBackend(sample_qubex_config)

        # Act
        circuit = QubexCircuit(backend)

        # Assert
        assert circuit._backend is backend

    def test_cx_gate_with_valid_pair(self, sample_qubex_config):
        """Test CX gate application with valid pair."""
        # Arrange
        backend = QubexBackend(sample_qubex_config)
        circuit = QubexCircuit(backend)

        # Act
        result = circuit.cx("Q00", "Q01")

        # Assert
        assert isinstance(result, PulseSchedule)

    def test_cx_gate_with_invalid_pair(self, sample_qubex_config):
        """Test CX gate raises error with invalid pair."""
        # Arrange
        backend = QubexBackend(sample_qubex_config)
        circuit = QubexCircuit(backend)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid qubits for CNOT: Q00, Q04"):
            circuit.cx("Q00", "Q04")

    def test_sx_gate_with_valid_qubit(self, sample_qubex_config):
        """Test SX gate application with valid qubit."""
        # Arrange
        backend = QubexBackend(sample_qubex_config)
        circuit = QubexCircuit(backend)

        # Act
        result = circuit.sx("Q00")

        # Assert
        assert isinstance(result, PulseSchedule)

    def test_sx_gate_with_invalid_qubit(self, sample_qubex_config):
        """Test SX gate raises error with invalid qubit."""
        # Arrange
        backend = QubexBackend(sample_qubex_config)
        circuit = QubexCircuit(backend)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid qubit: Q04"):
            circuit.sx("Q04")

    def test_barrier_returns_string(self, sample_qubex_config):
        """Test barrier method returns expected string."""
        # Arrange
        backend = QubexBackend(sample_qubex_config)
        circuit = QubexCircuit(backend)

        # Act
        result = circuit.barrier()

        # Assert
        assert result == "barrier"

    def test_delay_with_valid_parameters(self, sample_qubex_config):
        """Test delay application with valid parameters."""
        # Arrange
        backend = QubexBackend(sample_qubex_config)
        circuit = QubexCircuit(backend)

        # Act
        result = circuit.delay("Q00", 100.0)

        # Assert
        assert isinstance(result, PulseSchedule)

    def test_delay_with_invalid_qubit(self, sample_qubex_config):
        """Test delay raises error with invalid qubit."""
        # Arrange
        backend = QubexBackend(sample_qubex_config)
        circuit = QubexCircuit(backend)

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid qubit: Q04"):
            circuit.delay("Q04", 100.0)

    def test_compile_simple_circuit(self, sample_qubex_config):
        """Test compiling a simple quantum circuit."""
        # Arrange
        backend = QubexBackend(sample_qubex_config)
        circuit = QubexCircuit(backend)

        qc = QuantumCircuit(2, 2)
        qc.x(0)
        qc.cx(0, 1)
        qc.measure_all()

        # Act
        result = circuit.compile(qc)

        # Assert
        assert isinstance(result, PulseSchedule)
        ## Expected classical registers mapping for qubex manner:
        ##   0   0
        ## Q01 Q00
        expected_registers = ["Q01", "Q00"]
        assert backend.classical_registers == expected_registers
