"""
YARA scanner collector for ForensicHarvester.

Scans source files against YARA rules (``config['yara_rules']`` — a .yar file or a
directory of them) and writes matches to ``yara/yara_matches.jsonl``. Requires
``yara-python``; degrades to a warning if the library or rules are absent.
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone

from collectors.base import BaseCollector, CollectionResult
from utils.walk import iter_files

logger = logging.getLogger(__name__)

# Extensions worth scanning by default (avoid hashing every media file).
_SCAN_EXTS = [
    ".exe", ".dll", ".sys", ".scr", ".com", ".ps1", ".bat", ".cmd", ".vbs",
    ".js", ".jar", ".hta", ".wsf", ".doc", ".docm", ".xls", ".xlsm", ".rtf",
    ".pdf", ".lnk", ".tmp", ".dat", ".bin",
]


class YaraScannerCollector(BaseCollector):
    """Scan source files with YARA rules; emit matches as JSONL."""

    category = 'yara'

    def _get_time(self):
        return datetime.now()

    def _compile_rules(self):
        try:
            import yara  # type: ignore
        except ImportError:
            self.result.add_warning("yara-python not installed — skipping YARA scan")
            return None
        rules_path = self.config.get('yara_rules')
        if not rules_path or not os.path.exists(rules_path):
            self.result.add_warning("no yara_rules path configured — skipping YARA scan")
            return None
        try:
            if os.path.isdir(rules_path):
                filepaths = {}
                for dp, _d, files in os.walk(rules_path):
                    for f in files:
                        if f.lower().endswith((".yar", ".yara")):
                            filepaths[f] = os.path.join(dp, f)
                return yara.compile(filepaths=filepaths)
            return yara.compile(filepath=rules_path)
        except Exception as e:
            self.result.add_error(f"failed to compile YARA rules: {e}")
            return None

    def collect(self) -> CollectionResult:
        self.result.start_time = self._get_time()
        out_dir = self._ensure_output_dir()

        rules = self._compile_rules()
        if rules is None:
            self.result.end_time = self._get_time()
            return self.result

        jsonl_path = os.path.join(out_dir, "yara_matches.jsonl")
        max_files = int(self.config.get('yara_max_files', 50000))
        max_mb = int(self.config.get('yara_max_file_mb', 100))
        scanned = matched = 0

        with open(jsonl_path, "w", encoding="utf-8") as out:
            for root in self.source.roots():
                for rel, size in iter_files(self.source, root, max_files=max_files, exts=_SCAN_EXTS):
                    if max_mb and size > max_mb * 1024 * 1024:
                        continue
                    hits = self._scan_one(rules, rel)
                    scanned += 1
                    for m in hits:
                        out.write(json.dumps(m) + "\n")
                        matched += 1
                    if scanned >= max_files:
                        self.result.add_warning(f"yara scan capped at {max_files} files")
                        break

        self._register_derived_output(jsonl_path)
        self.result.details['files_scanned'] = scanned
        self.result.details['matches'] = matched
        logger.info("yara: scanned %d files, %d matches", scanned, matched)
        self.result.end_time = self._get_time()
        return self.result

    def _scan_one(self, rules, rel):
        """Extract a source file to temp and run YARA; return match records."""
        fd, tmp = tempfile.mkstemp(prefix="fh_yara_")
        os.close(fd)
        try:
            ok, _err = self.source.extract(rel, tmp)
            if not ok:
                return []
            matches = rules.match(tmp, timeout=60)
            return [
                {
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "path": rel,
                    "rule": m.rule,
                    "tags": list(getattr(m, "tags", [])),
                    "meta": dict(getattr(m, "meta", {})),
                }
                for m in matches
            ]
        except Exception as e:
            logger.debug("yara scan failed %s: %s", rel, e)
            return []
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
