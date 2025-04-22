"""Backend plugin manager."""

import importlib
import logging
from typing import Type

from device_gateway.core.base_backend import BaseBackend
from device_gateway.core.base_circuit import BaseCircuit

logger = logging.getLogger("device_gateway")

SUPPORTED_BACKENDS = ("qulacs", "qubex")  # Tuple of supported backend names


class BackendPluginManager:
    """Backend plugin manager."""

    def __init__(self):
        """Initialize plugin manager."""
        self._backends = {}

    def register_backend(self, name: str, backend_class: Type[BaseBackend]) -> None:
        """Register a backend plugin.

        Args:
            name: Backend name
            backend_class: Backend class
        """
        if not issubclass(backend_class, BaseBackend):
            raise ValueError(
                f"Backend class must inherit from BaseBackend: {backend_class}"
            )
        self._backends[name] = backend_class
        logger.info(f"Registered backend plugin: {name}")

    def get_backend(self, name: str, config: dict) -> BaseBackend:
        """Get a backend instance.

        Args:
            name: Backend name
            config: Backend configuration

        Returns:
            Backend instance

        Raises:
            ValueError: If backend is not found
        """
        if name not in self._backends:
            raise ValueError(f"Backend not found: {name}")
        return self._backends[name](config)

    def load_backend(self, name: str = "qulacs") -> None:
        """Load a backend plugin from a module path. Default is "qulacs".

        Args:
            name: Backend name

        Raises:
            ImportError: If module cannot be imported
            AttributeError: If class is not found in module
        """
        try:
            module_path = f"device_gateway.plugins.{name}.backend"
            class_name = f"{name.capitalize()}Backend"
            module = importlib.import_module(module_path)
            backend_class = getattr(module, class_name)
            self.register_backend(name, backend_class)
        except ImportError as e:
            logger.error(f"Failed to import backend module {module_path}: {e}")
            raise
        except AttributeError as e:
            logger.error(
                f"Failed to find backend class {class_name} in module {module_path}: {e}"
            )
            raise


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

    def load_circuit(self, name: str = "qulacs") -> None:
        """Load a circuit plugin from a module path. Default is "qulacs".

        Args:
            name: Circuit name

        Raises:
            ImportError: If module cannot be imported
            AttributeError: If class is not found in module
        """
        try:
            module_path = f"device_gateway.plugins.{name}.circuit"
            class_name = f"{name.capitalize()}Circuit"
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
