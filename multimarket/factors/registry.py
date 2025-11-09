"""Dynamic factor discovery utilities."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Dict, Iterable, Optional, Sequence, Type

from .base import BaseFactor


class FactorRegistry:
    """Collects available factor classes for use inside the platform."""

    def __init__(self) -> None:
        self._factors: Dict[str, Type[BaseFactor]] = {}

    def register(self, factor_cls: Type[BaseFactor]) -> None:
        self._factors[factor_cls.__name__] = factor_cls

    def available(self) -> Sequence[str]:
        return tuple(sorted(self._factors))

    def get(self, name: str) -> Type[BaseFactor]:
        if name not in self._factors:
            raise KeyError(f"Factor '{name}' is not registered")
        return self._factors[name]

    def create(self, name: str, params: Optional[dict] = None) -> BaseFactor:
        factor_cls = self.get(name)
        return factor_cls(params=params)

    def load_path(self, path: Path) -> None:
        """Load factor classes from ``path`` recursively."""

        if path.is_file() and path.suffix == ".py":
            module = _module_from_file(path)
            self._register_module_factors(module)
            return
        for file in path.rglob("*.py"):
            if file.name.startswith("__"):
                continue
            module = _module_from_file(file)
            self._register_module_factors(module)

    def _register_module_factors(self, module: ModuleType) -> None:
        for attr in module.__dict__.values():
            if isinstance(attr, type) and issubclass(attr, BaseFactor) and attr is not BaseFactor:
                self.register(attr)


def _module_from_file(file: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(file.stem, file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import module from {file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[file.stem] = module
    spec.loader.exec_module(module)
    return module


GLOBAL_FACTOR_REGISTRY = FactorRegistry()
