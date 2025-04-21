"""Circuit plugin manager."""

import importlib
import logging
from typing import Type

from device_gateway.circuit.base_circuit import BaseCircuit

logger = logging.getLogger("device_gateway")


class CircuitPluginManager:
    """Circuit plugin manager."""

    def __init__(self):
        """Initialize plugin manager."""
        self._circuits = {}

    def register_circuit(self, name: str, circuit_class: Type[BaseCircuit]) -> None:
        """Register a circuit plugin.

        Args:
            name: Circuit name
            circuit_class: Circuit class
        """
        if not issubclass(circuit_class, BaseCircuit):
            raise ValueError(
                f"Circuit class must inherit from BaseCircuit: {circuit_class}"
            )
        self._circuits[name] = circuit_class
        logger.info(f"Registered circuit plugin: {name}")

    def get_circuit(self, name: str, backend) -> BaseCircuit:
        """Get a circuit instance.

        Args:
            name: Circuit name
            backend: Backend instance for the circuit

        Returns:
            Circuit instance

        Raises:
            ValueError: If circuit is not found
        """
        if name not in self._circuits:
            raise ValueError(f"Circuit not found: {name}")
        return self._circuits[name](backend)

    def load_circuit_from_path(
        self, name: str, module_path: str, class_name: str
    ) -> None:
        """Load a circuit plugin from a module path.

        Args:
            name: Circuit name
            module_path: Module path (e.g., "device_gateway.circuit.qulacs_circuit")
            class_name: Class name (e.g., "QulacsCircuit")

        Raises:
            ImportError: If module cannot be imported
            AttributeError: If class is not found in module
        """
        try:
            module = importlib.import_module(module_path)
            circuit_class = getattr(module, class_name)
            self.register_circuit(name, circuit_class)
        except ImportError as e:
            logger.error(f"Failed to import circuit module {module_path}: {e}")
            raise
        except AttributeError as e:
            logger.error(
                f"Failed to find circuit class {class_name} in module {module_path}: {e}"
            )
            raise
