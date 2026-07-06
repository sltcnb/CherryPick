"""The previously-stub collectors now produce real derived artifacts."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sources import build_source  # noqa: E402
from utils.manifest import CollectionManifest  # noqa: E402
from collectors.hashing import HashingCollector  # noqa: E402
from collectors.file_listing import FileListingCollector  # noqa: E402
from collectors.file_search import FileSearchCollector  # noqa: E402


def _tree():
    src = tempfile.mkdtemp()
    os.makedirs(os.path.join(src, "a"))
    with open(os.path.join(src, "a", "x.exe"), "wb") as fh:
        fh.write(b"MZ payload")
    with open(os.path.join(src, "a", "mimikatz.txt"), "w") as fh:
        fh.write("secrets")
    return src


def _run(cls, cfg, src, out):
    cfg = dict(cfg)
    cfg["_source"] = build_source(src)
    man = CollectionManifest(out, "exhaustive")
    c = cls(cfg, src, out, "exhaustive", man)
    return c.run()


def test_hashing_produces_inventory():
    src, out = _tree(), tempfile.mkdtemp()
    r = _run(HashingCollector, {"level": "exhaustive", "hash_collected": True}, src, out)
    assert r.details["files_hashed"] >= 2
    assert os.path.exists(os.path.join(out, "hashing", "hashes.csv"))


def test_file_listing_produces_csv():
    src, out = _tree(), tempfile.mkdtemp()
    r = _run(FileListingCollector, {"level": "exhaustive"}, src, out)
    assert r.details["files_listed"] >= 2
    assert os.path.exists(os.path.join(out, "file_listing", "file_listing.csv"))


def test_file_search_matches_glob():
    src, out = _tree(), tempfile.mkdtemp()
    r = _run(FileSearchCollector, {"fetch": ["mimikatz*"], "fetch_root": ""}, src, out)
    assert r.details["matches"] == 1


if __name__ == "__main__":
    test_hashing_produces_inventory()
    test_file_listing_produces_csv()
    test_file_search_matches_glob()
    print("PASS stub collectors")
