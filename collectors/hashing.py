"""
Hashing collector for ForensicHarvester.

Produces a hash inventory (MD5 + SHA-256 + size) of files under the source,
rather than copying them. Output: ``hashing/hashes.csv``. Bounded by level:

* small       -> executables only (.exe/.dll/.sys/.scr)
* complete    -> executables + scripts (.ps1/.bat/.vbs/.js/.jar)
* exhaustive  -> every file (subject to caps)
"""

import csv
import hashlib
import logging
import os
from datetime import datetime

from collectors.base import BaseCollector, CollectionResult
from utils.walk import iter_files

logger = logging.getLogger(__name__)

_EXE = [".exe", ".dll", ".sys", ".scr", ".com"]
_SCRIPT = [".ps1", ".bat", ".cmd", ".vbs", ".js", ".jar", ".hta", ".wsf"]

_READ = 1024 * 1024


class HashingCollector(BaseCollector):
    """Emit a hash inventory of source files (no file copies)."""

    category = 'hashing'

    def _get_time(self):
        return datetime.now()

    def _exts_for_level(self):
        if self.level == 'small':
            return _EXE
        if self.level == 'complete':
            return _EXE + _SCRIPT
        return None  # exhaustive: everything

    def _hashes(self, path: str):
        """MD5+SHA256 of a source file, streamed via a temporary extract."""
        import tempfile
        fd, tmp = tempfile.mkstemp(prefix="fh_hash_")
        os.close(fd)
        try:
            ok, _err = self.source.extract(path, tmp)
            if not ok:
                return None, None
            md5 = hashlib.md5()
            sha = hashlib.sha256()
            with open(tmp, "rb") as fh:
                for block in iter(lambda: fh.read(_READ), b""):
                    md5.update(block)
                    sha.update(block)
            return md5.hexdigest(), sha.hexdigest()
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass

    def collect(self) -> CollectionResult:
        self.result.start_time = self._get_time()
        out_dir = self._ensure_output_dir()
        csv_path = os.path.join(out_dir, "hashes.csv")

        max_files = int(self.config.get('hash_max_files', 20000))
        exts = self._exts_for_level()
        roots = self.source.roots()
        n = 0
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["path", "size", "md5", "sha256"])
            for root in roots:
                for rel, size in iter_files(self.source, root, max_files=max_files, exts=exts):
                    md5, sha = self._hashes(rel)
                    if sha is None:
                        continue
                    w.writerow([rel, size, md5, sha])
                    n += 1
                    if n >= max_files:
                        self.result.add_warning(f"hashing capped at {max_files} files")
                        break

        self._register_derived_output(csv_path)
        self.result.details['files_hashed'] = n
        logger.info("hashing: inventoried %d files", n)
        self.result.end_time = self._get_time()
        return self.result
