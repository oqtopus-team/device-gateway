import logging
from typing import TYPE_CHECKING

from device_gateway.core.base_circuit import BaseCircuit

if TYPE_CHECKING:
    from device_gateway.plugins.ybex.backend import YbexBackend

logger = logging.getLogger("device_gateway")

SUPPORTED_GATES = ["rx", "measure"]


class YbexCircuit(BaseCircuit):
    """Ybex circuit implementation."""

    def __init__(self, backend: "YbexBackend"):
        """Initialize the circuit with backend.

        Args:
            backend: Backend to execute the circuit on
        """
        self._backend = backend
        self._angle = 0.0

    def rx(self, target: int, angle: float) -> None:
        """Apply RX gate."""
        if target not in self._backend.qubits:
            logger.error(f"Invalid qubit: {target}")
            raise ValueError(f"Invalid qubit: {target}")
        logger.debug(f"Applying RX gate: Physical qubit: {target}, angle={angle}")
        self._angle += angle
