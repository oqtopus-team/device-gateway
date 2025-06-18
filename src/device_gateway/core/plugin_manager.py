"""Backend plugin manager."""

import importlib
import logging
from typing import Any, Dict, Optional, Type

from device_gateway.core.base_backend import BaseBackend

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

    def get_backend(self, name: str, config: Dict[str, Any]) -> BaseBackend:
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

    def load_backend(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Load a backend plugin from a module path.

        Args:
            config: Configuration dictionary containing backend settings

        Raises:
            ImportError: If module cannot be imported
            AttributeError: If class is not found in module
            ValueError: If backend configuration is invalid
        """
        try:
            if config is None:
                config = {}

            plugin_config = config.get("plugin", {})
            if not plugin_config:
                raise ValueError("Plugin configuration is missing")

            name = plugin_config.get("name", "qulacs")
            backend_settings = plugin_config.get("backend", {})
            default_module_path = f"device_gateway.plugins.{name}.backend"
            default_class_name = f"{name.capitalize()}Backend"

            module_path = backend_settings.get("module_path", default_module_path)
            class_name = backend_settings.get("class_name", default_class_name)
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
