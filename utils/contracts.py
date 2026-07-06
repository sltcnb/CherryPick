"""
Contract loading + validation for Triager.

FH is self-contained: it vendors its own copy of the Citadel contract files
under ``contracts/`` (``bundle_manifest.schema.json``, ``forensic_event.schema.json``,
``collector.proto``). This module resolves and loads those files whether running
from source or from a PyInstaller ``--onefile`` binary, and validates payloads
against them.

Validation degrades gracefully: if ``jsonschema`` is not installed the loaders
still return the schema dict and ``validate_bundle_manifest`` performs a minimal
required-key check instead of a full schema validation.
"""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

BUNDLE_MANIFEST_SCHEMA = "bundle_manifest.schema.json"
FORENSIC_EVENT_SCHEMA = "forensic_event.schema.json"
COLLECTOR_PROTO = "collector.proto"


def contracts_dir() -> Path:
    """Locate the vendored ``contracts/`` directory (source or frozen binary)."""
    # PyInstaller --onefile unpacks bundled data under sys._MEIPASS.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cand = Path(meipass) / "contracts"
        if cand.is_dir():
            return cand
    # Allow an explicit override (dev/testing).
    env = os.environ.get("FH_CONTRACTS_DIR")
    if env:
        return Path(env)
    # Source layout: <repo>/contracts, this file is <repo>/utils/contracts.py
    return Path(__file__).resolve().parent.parent / "contracts"


def _load_schema(name: str) -> Dict[str, Any]:
    path = contracts_dir() / name
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=None)
def bundle_manifest_schema() -> Dict[str, Any]:
    return _load_schema(BUNDLE_MANIFEST_SCHEMA)


@lru_cache(maxsize=None)
def forensic_event_schema() -> Dict[str, Any]:
    return _load_schema(FORENSIC_EVENT_SCHEMA)


class ContractValidationError(ValueError):
    """Raised when a payload does not conform to its contract."""


def _minimal_check(manifest: Dict[str, Any]) -> None:
    """Fallback validation when jsonschema is unavailable."""
    required = ["session_id", "hostname", "os", "started_at", "artifacts", "artifact_count"]
    missing = [k for k in required if k not in manifest]
    if missing:
        raise ContractValidationError(f"manifest missing required keys: {missing}")
    if manifest["os"] not in ("windows", "linux", "macos", "cloud", "unknown"):
        raise ContractValidationError(f"invalid os enum: {manifest['os']!r}")
    for i, art in enumerate(manifest["artifacts"]):
        for k in ("name", "sha256", "size", "category"):
            if k not in art:
                raise ContractValidationError(f"artifacts[{i}] missing {k!r}")


def validate_bundle_manifest(manifest: Dict[str, Any]) -> None:
    """Validate a bundle manifest dict against the vendored schema.

    Raises :class:`ContractValidationError` on failure. Uses ``jsonschema`` when
    available; otherwise falls back to a minimal required-key check.
    """
    try:
        import jsonschema  # type: ignore
    except ImportError:
        _minimal_check(manifest)
        return
    try:
        jsonschema.validate(instance=manifest, schema=bundle_manifest_schema())
    except jsonschema.ValidationError as exc:  # type: ignore[attr-defined]
        raise ContractValidationError(str(exc)) from exc
