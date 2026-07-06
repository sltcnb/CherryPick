"""
HarvesterCollection — the single collection orchestrator.

Implements the pluggable :class:`~collectors.artifact_collector.ArtifactCollector`
lifecycle at the *run* level (mirroring Talon's adapter pattern, but for the whole
session rather than one legacy object):

    start()     → resolve the requested category keys to collector classes
    collect()   → run each per-category BaseCollector (threaded for live sources,
                  sequential for pytsk3 image/raw sources)
    finalize()  → build a contract-conformant SessionResult from the manifest's
                  successful entries (maps FH's base.CollectionResult stats onto
                  the session-level manifest without unifying the two dataclasses)

This replaces the ad-hoc ``COLLECTOR_CLASSES`` dispatch + ``_run_collectors`` loop
that used to live in ``forensic_harvester.py``.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from collectors import collector_registry as registry
from collectors.artifact_collector import ArtifactCollector, ArtifactRef, SessionResult, sha256_file
from utils.manifest import CollectionManifest

logger = logging.getLogger(__name__)


class HarvesterCollection(ArtifactCollector):
    """Runs the selected per-category collectors and seals a session manifest."""

    def __init__(
        self,
        config: Dict,
        source_root: str,
        output_root: str,
        level: str,
        manifest: CollectionManifest,
        category_keys: List[str],
        *,
        image: Any = None,
        source: Any = None,
        session_id: Optional[str] = None,
        hostname: Optional[str] = None,
        os_name: Optional[str] = None,
        threads: int = 4,
        progress: bool = False,
    ) -> None:
        super().__init__(
            session_id or _default_session_id(),
            hostname=hostname,
            os_name=os_name,
        )
        self.config = dict(config) if isinstance(config, dict) else config
        self.source_root = source_root
        self.output_root = output_root
        self.level = level
        self.manifest = manifest
        self.image = image
        self.source = source
        # A prepared Source is injected into collectors and drives threading.
        if source is not None and isinstance(self.config, dict):
            self.config['_source'] = source
        self.threads = max(1, int(threads))
        self.progress = progress
        self._requested = list(category_keys)
        self._resolved: Dict[str, Any] = {}
        self._results: List[Any] = []  # base.CollectionResult per collector

    # ── ArtifactCollector API ────────────────────────────────────────────────
    def categories(self) -> Set[str]:
        return {registry.resolve_key(k) for k in self._requested}

    def start(self) -> None:
        for key in self._requested:
            cls = registry.get(key)
            if cls is None:
                self.result.errors.append(f"unknown category: {key}")
                logger.warning("orchestrator: no collector for category %r", key)
                continue
            self._resolved[registry.resolve_key(key)] = cls

    def collect(self) -> None:
        # pytsk3 is not thread-safe: image/raw sources run sequentially.
        seq_source = getattr(self.source, "sequential", False)
        sequential = self.image is not None or seq_source or self.threads == 1
        if sequential:
            for key, cls in self._resolved.items():
                self._run_one(key, cls)
        else:
            with ThreadPoolExecutor(max_workers=self.threads) as pool:
                futs = {
                    pool.submit(self._run_one, key, cls): key
                    for key, cls in self._resolved.items()
                }
                for fut in as_completed(futs):
                    key = futs[fut]
                    try:
                        fut.result()
                    except Exception as exc:  # already logged in _run_one
                        self.result.errors.append(f"{key}: {exc}")

    def finalize(self) -> SessionResult:
        """Build the session manifest from successful manifest entries."""
        for entry in self.manifest.entries:
            if entry.status != "success":
                continue
            sha = entry.sha256
            size = entry.size_bytes
            if not sha:
                # Hashing was disabled for this file — hash the staged copy now
                # so the manifest stays schema-valid (sha256 is required).
                dest = Path(self.output_root) / entry.dest_path
                try:
                    sha = sha256_file(dest)
                    if not size:
                        size = dest.stat().st_size
                except OSError as exc:
                    self.result.errors.append(f"hash failed {entry.dest_path}: {exc}")
                    continue
            self.result.artifacts.append(
                ArtifactRef(
                    name=entry.dest_path.replace(os.sep, "/"),
                    sha256=sha,
                    size=size,
                    category=entry.category,
                )
            )
        for err in self.manifest.errors:
            self.result.errors.append(str(err))
        self.result.finished_at = _now()
        return self.result

    # ── internals ──────────────────────────────────────────────────────────
    def _run_one(self, key: str, cls) -> None:
        try:
            collector = cls(
                self.config,
                self.source_root if self.image is None else "/",
                self.output_root,
                self.level,
                self.manifest,
                self.image,
            )
            if not collector.should_collect():
                return
            if self.progress:
                logger.info("collecting %s ...", key)
            result = collector.run()
            self._results.append(result)
        except Exception as exc:
            logger.exception("orchestrator: collector %r failed", key)
            self.manifest.add_error(f"{key}: {exc}")
            raise


def _default_session_id() -> str:
    # datetime.now() is fine here (real run); avoids extra deps.
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _now() -> str:
    from collectors.artifact_collector import now_iso

    return now_iso()
