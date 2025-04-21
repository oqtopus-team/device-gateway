"""Backend plugin manager."""

import importlib
import logging
from typing import Type

from device_gateway.backend.base_backend import BaseBackend

logger = logging.getLogger("device_gateway")


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

    def load_backend_from_path(
        self, name: str, module_path: str, class_name: str
    ) -> None:
        """Load a backend plugin from a module path.

        Args:
            name: Backend name
            module_path: Module path (e.g., "device_gateway.backend.qulacs_backend")
            class_name: Class name (e.g., "QulacsBackend")

        Raises:
            ImportError: If module cannot be imported
            AttributeError: If class is not found in module
        """
        try:
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
