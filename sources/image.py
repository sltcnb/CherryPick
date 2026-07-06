"""pytsk3 disk-image source (E01/dd/vhd) — wraps utils.image_utils.DiskImage."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from sources.base import Source

logger = logging.getLogger(__name__)


class ImageSource(Source):
    """Artifacts read from a pytsk3-backed disk image.

    Behaviour matches the pre-refactor ``self.image`` branch of ``BaseCollector``
    exactly. pytsk3 is not thread-safe, so ``sequential = True``.
    """

    sequential = True

    def __init__(self, image):
        self.image = image  # utils.image_utils.DiskImage

    def expand(self, path: str) -> str:
        # Image paths are addressed raw (normalized inside DiskImage); no join.
        return path

    def exists(self, path: str) -> bool:
        return bool(self.image and self.image.file_exists(path))

    def is_file(self, path: str) -> bool:
        if not self.image or not self.image.file_exists(path):
            return False
        entries = self.image.list_files(path)
        real = [e for e in entries if e.get("name") not in (".", "..")]
        # A path that lists no children is treated as a file (matches legacy heuristic).
        return len(real) == 0

    def list_dir(self, path: str) -> List[str]:
        if not self.image:
            return []
        return [e["name"] for e in self.image.list_files(path)]

    def file_size(self, path: str) -> int:
        if not self.image:
            return 0
        return self.image.get_file_size(path)

    def extract(self, src_path: str, dest_path: str) -> Tuple[bool, Optional[str]]:
        if not self.image:
            return False, "no image"
        if self.image.extract_file(src_path, dest_path):
            return True, None
        return False, "Failed to extract from image"

    def roots(self) -> List[str]:
        return ["/"]

    def close(self) -> None:
        try:
            if self.image:
                self.image.close()
        except Exception:
            pass
