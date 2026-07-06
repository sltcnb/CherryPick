"""Source ABC — the primitive filesystem operations every collector relies on."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# User-profile directory names that are never real interactive users.
_NON_USER_PROFILES = {
    "public", "default", "default user", "all users", "defaultuser0",
    "systemprofile", "localservice", "networkservice",
}


class Source(ABC):
    """Abstract artifact source (live / mounted / image / raw device).

    The primitives mirror exactly what ``collectors.base.BaseCollector`` used to
    branch on ``self.image`` for; collectors now delegate here and stay agnostic
    to where the bytes come from.
    """

    #: pytsk3 is not thread-safe; image/raw sources set this True so the
    #: orchestrator runs their collectors sequentially.
    sequential: bool = False

    # ── lifecycle ────────────────────────────────────────────────────────────
    def open(self) -> "Source":
        """Prepare the source (mount/unlock). Returns self. Default no-op."""
        return self

    def close(self) -> None:
        """Release the source (unmount/cleanup). Default no-op."""

    # ── path helpers ─────────────────────────────────────────────────────────
    @abstractmethod
    def expand(self, path: str) -> str:
        """Resolve a source-relative path to whatever this source addresses with."""

    # ── primitives ───────────────────────────────────────────────────────────
    @abstractmethod
    def exists(self, path: str) -> bool: ...

    @abstractmethod
    def is_file(self, path: str) -> bool: ...

    @abstractmethod
    def list_dir(self, path: str) -> List[str]: ...

    @abstractmethod
    def file_size(self, path: str) -> int: ...

    @abstractmethod
    def extract(self, src_path: str, dest_path: str) -> Tuple[bool, Optional[str]]:
        """Copy/extract a source file to a local destination path."""

    # ── discovery ────────────────────────────────────────────────────────────
    @abstractmethod
    def roots(self) -> List[str]:
        """Top-level roots to scan (drive letters / volume root)."""

    def iter_users(self, users_dir: str = "Users") -> List[str]:
        """Enumerate interactive user-profile directory names under ``users_dir``.

        Default implementation lists ``<root>/Users`` and filters service/system
        profiles. Overridable per-OS (Linux ``/home``, macOS ``/Users``).
        """
        names: List[str] = []
        for entry in self.list_dir(users_dir):
            if entry.lower() in _NON_USER_PROFILES:
                continue
            if self.exists(f"{users_dir}/{entry}") and not self.is_file(f"{users_dir}/{entry}"):
                names.append(entry)
        return names
