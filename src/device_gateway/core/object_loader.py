"""Helpers for loading configured Python objects."""

from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from typing import Any


def load_object(spec: Mapping[str, Any]) -> Any:
    """Load an object from a config mapping.

    Supported forms:
      - ``class: "pkg.module.Class"`` with optional ``kwargs``.
      - ``module_path`` + ``class_name`` with optional ``kwargs``.
      - either class form plus ``factory`` to call a classmethod.
      - ``module_path`` + ``factory`` to call a module-level factory.
    """
    kwargs = resolve_references(dict(spec.get("kwargs", {})))
    class_ref = spec.get("class")
    module_path = spec.get("module_path")
    class_name = spec.get("class_name")
    factory_name = spec.get("factory")

    if class_ref:
        target = import_ref(str(class_ref))
        if factory_name:
            return getattr(target, str(factory_name))(**kwargs)
        return target(**kwargs)

    if not module_path:
        raise ValueError("Object spec requires class or module_path.")

    module = importlib.import_module(str(module_path))
    if class_name:
        target = getattr(module, str(class_name))
        if factory_name:
            return getattr(target, str(factory_name))(**kwargs)
        return target(**kwargs)

    if factory_name:
        return getattr(module, str(factory_name))(**kwargs)

    raise ValueError("Object spec requires class_name or factory when using module_path.")


def import_ref(ref: str) -> Any:
    """Import ``module.attr`` and return the referenced object."""
    module_name, _, attr_name = ref.rpartition(".")
    if not module_name or not attr_name:
        raise ValueError(f"Invalid import reference: {ref!r}")
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def resolve_references(value: Any) -> Any:
    """Resolve nested ``class_ref`` mappings inside config values."""
    if isinstance(value, Mapping):
        if set(value) == {"class_ref"}:
            return import_ref(str(value["class_ref"]))
        return {key: resolve_references(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [resolve_references(item) for item in value]
    return value
