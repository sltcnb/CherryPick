"""
Bounded filesystem walk over the unified Source abstraction.

Used by the derived-artifact collectors (hashing, file_listing, yara) which must
enumerate many files regardless of source type. For a local filesystem
(:class:`~sources.live.LiveFilesystemSource`) it uses fast ``os.walk``; for a
pytsk3 image or other source it falls back to a Source-primitive BFS.

All walks are bounded by ``max_files`` and a per-walk deadline to keep triage
predictable; callers should ``log`` when a cap truncates coverage.
"""

from __future__ import annotations

import os
import time
from typing import Iterator, List, Optional, Tuple

from sources.live import LiveFilesystemSource


def iter_files(
    source,
    root: str,
    *,
    max_files: int = 100000,
    deadline_s: float = 600.0,
    exts: Optional[List[str]] = None,
) -> Iterator[Tuple[str, int]]:
    """Yield ``(source_relative_path, size)`` for files under ``root``.

    ``exts`` (lowercase, with dot) filters by extension when given.
    """
    started = time.monotonic()
    count = 0
    ext_set = {e.lower() for e in exts} if exts else None

    if isinstance(source, LiveFilesystemSource):
        base = source.expand(root)
        for dirpath, _dirs, files in os.walk(base):
            for name in files:
                if ext_set and os.path.splitext(name)[1].lower() not in ext_set:
                    continue
                full = os.path.join(dirpath, name)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    continue
                rel = os.path.relpath(full, base)
                yield rel.replace(os.sep, "/"), size
                count += 1
                if count >= max_files or (time.monotonic() - started) > deadline_s:
                    return
        return

    # Generic BFS via Source primitives (pytsk3 image / mounted / raw).
    stack = [root.rstrip("/") or ""]
    while stack:
        cur = stack.pop()
        for name in source.list_dir(cur):
            if name in (".", ".."):
                continue
            child = f"{cur}/{name}" if cur else name
            if source.is_file(child):
                if ext_set and os.path.splitext(name)[1].lower() not in ext_set:
                    continue
                yield child, source.file_size(child)
                count += 1
                if count >= max_files or (time.monotonic() - started) > deadline_s:
                    return
            else:
                stack.append(child)
