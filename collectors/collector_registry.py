"""
Collector registry for Triager.

Replaces the old three-place static dispatch (``COLLECTOR_CLASSES`` in
``triager.py``, ``CATEGORY_COLLECTOR_MAP`` in ``utils/constants.py``
and the re-exports in ``collectors/__init__.py``) with a single source of truth:
auto-discovery of every :class:`~collectors.base.BaseCollector` subclass in the
``collectors`` package, keyed by its declared ``category``.

Adding a collector now means dropping one file in ``collectors/`` — no edits to
any dispatch table.

Category keys
-------------
Talon's ``capabilities.yaml`` keys are treated as canonical (``evtx``,
``network_cfg``, ``yara``, …). FH's historical collector ``category`` strings
(``eventlogs``, ``network``, ``yara_scanner``, …) are kept working via
:data:`CANONICAL_ALIASES`, so ``get()`` resolves either spelling.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import Dict, Iterable, List, Optional, Set, Type

from collectors.base import BaseCollector

logger = logging.getLogger(__name__)

# Canonical (Talon capabilities.yaml) key  ->  FH native collector category.
# Lets `--collect evtx` resolve FH's EventLogsCollector (category 'eventlogs').
CANONICAL_ALIASES: Dict[str, str] = {
    "evtx": "eventlogs",
    "network_cfg": "network",
    "yara_scanner": "yara",
    "scheduled_tasks": "persistence",
    "tasks": "persistence",
    # Talon/short messaging keys -> FH native `messaging_*` collector categories.
    "teams": "messaging_teams",
    "slack": "messaging_slack",
    "discord": "messaging_discord",
    "signal": "messaging_signal",
    "whatsapp": "messaging_whatsapp",
    "telegram": "messaging_telegram",
}

_REGISTRY: Optional[Dict[str, Type[BaseCollector]]] = None


def _discover() -> Dict[str, Type[BaseCollector]]:
    """Import every module in the collectors package and map category -> class."""
    import collectors  # local import to avoid a cycle at module load

    mapping: Dict[str, Type[BaseCollector]] = {}
    skip = {"base", "collector_registry", "orchestrator", "artifact_collector"}

    for mod in pkgutil.iter_modules(collectors.__path__):
        if mod.name in skip or mod.name.startswith("_"):
            continue
        try:
            module = importlib.import_module(f"collectors.{mod.name}")
        except Exception as exc:  # a broken collector must not kill discovery
            logger.warning("registry: failed to import collectors.%s: %s", mod.name, exc)
            continue
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(cls, BaseCollector)
                and cls is not BaseCollector
                and cls.__module__ == module.__name__
                and not cls.__name__.startswith("_")   # skip intermediate bases
                and cls.category not in ("base", "")    # skip un-keyed abstracts
            ):
                for key in cls.supported_categories():
                    if key in mapping and mapping[key] is not cls:
                        logger.warning(
                            "registry: category %r claimed by both %s and %s",
                            key, mapping[key].__name__, cls.__name__,
                        )
                    mapping[key] = cls
    return mapping


def registry() -> Dict[str, Type[BaseCollector]]:
    """Return the (cached) category-key -> collector-class map."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _discover()
        logger.debug("registry: discovered %d collectors", len(_REGISTRY))
    return _REGISTRY


def resolve_key(key: str) -> str:
    """Map a (possibly canonical/alias) key to a native collector category."""
    reg = registry()
    if key in reg:
        return key
    return CANONICAL_ALIASES.get(key, key)


def get(key: str) -> Optional[Type[BaseCollector]]:
    """Look up a collector class by native or canonical/alias key."""
    return registry().get(resolve_key(key))


def all_keys() -> Set[str]:
    """Every native category key that has a registered collector."""
    return set(registry().keys())


def resolve_many(keys: Iterable[str]) -> "Dict[str, Optional[Type[BaseCollector]]]":
    """Resolve a batch of requested keys to classes (None for unknown)."""
    return {k: get(k) for k in keys}


def validate_against_capabilities(capability_keys: Iterable[str]) -> List[str]:
    """Return human-readable drift between capabilities.yaml and the registry.

    Every capability option value must resolve to a registered collector, and
    every registered collector should appear in the catalog. Returns a list of
    problem strings (empty == consistent). This is what catches drift like the
    old ``VPNICollector`` typo at startup.
    """
    problems: List[str] = []
    cap = set(capability_keys)
    for key in sorted(cap):
        if get(key) is None:
            problems.append(f"capabilities key {key!r} has no registered collector")
    resolved_cap = {resolve_key(k) for k in cap}
    for key in sorted(all_keys()):
        if key not in resolved_cap:
            problems.append(f"registered collector {key!r} is absent from capabilities.yaml")
    return problems
