"""
FileListing collector for ForensicHarvester.

Produces a full recursive file listing with MACB timestamps and size, as a CSV
under ``file_listing/file_listing.csv``. Works over any source (live/mounted via
``os.walk``, pytsk3 image via Source primitives).
"""

import csv
import logging
import os
from datetime import datetime, timezone

from collectors.base import BaseCollector, CollectionResult
from sources.live import LiveFilesystemSource
from utils.walk import iter_files

logger = logging.getLogger(__name__)


def _iso(ts):
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        return ""


class FileListingCollector(BaseCollector):
    """Recursive file listing with MACB timestamps."""

    category = 'file_listing'

    def _get_time(self):
        return datetime.now()

    def collect(self) -> CollectionResult:
        self.result.start_time = self._get_time()
        out_dir = self._ensure_output_dir()
        csv_path = os.path.join(out_dir, "file_listing.csv")

        max_files = int(self.config.get('listing_max_files', 500000))
        live = isinstance(self.source, LiveFilesystemSource)
        n = 0
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["path", "size", "modified", "accessed", "changed"])
            for root in self.source.roots():
                for rel, size in iter_files(self.source, root, max_files=max_files):
                    mtime = atime = ctime = ""
                    if live:
                        try:
                            st = os.stat(os.path.join(self.source.expand(root), rel))
                            mtime, atime, ctime = _iso(st.st_mtime), _iso(st.st_atime), _iso(st.st_ctime)
                        except OSError:
                            pass
                    w.writerow([rel, size, mtime, atime, ctime])
                    n += 1
                    if n >= max_files:
                        self.result.add_warning(f"file_listing capped at {max_files} entries")
                        break

        self._register_derived_output(csv_path)
        self.result.details['files_listed'] = n
        logger.info("file_listing: listed %d entries", n)
        self.result.end_time = self._get_time()
        return self.result
