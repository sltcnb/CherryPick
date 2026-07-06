"""
IOC file-search collector (Talon ``--fetch`` parity).

Sweeps the source for files matching operator-supplied patterns and collects the
matches into ``file_search/``. Patterns (config ``fetch``, a list) may be:

* ``re:<regex>``  — regex matched against the full path
* ``*.ps1`` / ``mimikatz*`` — shell-style glob on the basename
* ``exactname.exe`` — exact basename match

Bounded by ``fetch_max_files``, ``fetch_max_mb`` and a wall-clock deadline.
"""

import fnmatch
import logging
import os
import re
import time
from datetime import datetime

from collectors.base import BaseCollector, CollectionResult
from utils.walk import iter_files

logger = logging.getLogger(__name__)


class FileSearchCollector(BaseCollector):
    """Collect files matching IOC name/glob/regex patterns."""

    category = 'file_search'

    def _get_time(self):
        return datetime.now()

    def _compile(self):
        regexes, globs, exact = [], [], set()
        for pat in self.config.get('fetch', []) or []:
            if pat.startswith('re:'):
                try:
                    regexes.append(re.compile(pat[3:], re.IGNORECASE))
                except re.error as e:
                    self.result.add_warning(f"bad regex {pat!r}: {e}")
            elif any(ch in pat for ch in '*?['):
                globs.append(pat.lower())
            else:
                exact.add(pat.lower())
        return regexes, globs, exact

    def _matches(self, rel, regexes, globs, exact):
        name = os.path.basename(rel).lower()
        if name in exact:
            return True
        if any(fnmatch.fnmatch(name, g) for g in globs):
            return True
        if any(rx.search(rel) for rx in regexes):
            return True
        return False

    def collect(self) -> CollectionResult:
        self.result.start_time = self._get_time()
        if not (self.config.get('fetch')):
            self.result.add_warning("file_search selected but no --fetch patterns given")
            self.result.end_time = self._get_time()
            return self.result

        regexes, globs, exact = self._compile()
        max_files = int(self.config.get('fetch_max_files', 200))
        max_mb = int(self.config.get('fetch_max_mb', 100))
        deadline = 600.0
        root = self.config.get('fetch_root') or (self.source.roots()[0] if self.source.roots() else '/')

        started = time.monotonic()
        found = 0
        for rel, size in iter_files(self.source, root, max_files=10_000_000, deadline_s=deadline):
            if (time.monotonic() - started) > deadline:
                self.result.add_warning("file_search hit 600s deadline")
                break
            if max_mb and size > max_mb * 1024 * 1024:
                continue
            if not self._matches(rel, regexes, globs, exact):
                continue
            dest_name = rel.replace('/', '_')
            if self._collect_file(rel, '', dest_name):
                found += 1
            if found >= max_files:
                self.result.add_warning(f"file_search capped at {max_files} files")
                break

        self.result.details['matches'] = found
        logger.info("file_search: collected %d matching files", found)
        self.result.end_time = self._get_time()
        return self.result
