"""Cross-platform behaviour of the long-path helper (utils.file_ops.extend_path)."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.file_ops import extend_path  # noqa: E402


def test_extend_path_unchanged_on_posix(monkeypatch):
    """On macOS/Linux the \\\\?\\ Windows long-path prefix must never be applied.

    Regression test: extend_path() used to call os.path.abspath() and
    unconditionally prepend the Windows-only "\\\\?\\" long-path prefix once a
    path exceeded 260 characters, regardless of OS. On POSIX that prefix is
    not a valid path component, so every subsequent open()/stat() on it
    raised OSError, silently dropping evidence during a live collection on
    macOS/Linux.
    """
    monkeypatch.setattr(os, "name", "posix")
    long_path = "/tmp/" + ("a" * 300)  # comfortably over MAX_PATH (260)
    assert extend_path(long_path) == long_path
    assert not extend_path(long_path).startswith("\\\\?\\")


def test_extend_path_short_posix_path_unchanged(monkeypatch):
    monkeypatch.setattr(os, "name", "posix")
    short_path = "/tmp/hosts"
    assert extend_path(short_path) == short_path


def test_extend_path_empty_string_unchanged(monkeypatch):
    monkeypatch.setattr(os, "name", "posix")
    assert extend_path("") == ""


def test_extend_path_prefixes_long_windows_path(monkeypatch, tmp_path):
    """On Windows, long paths still get the \\\\?\\ prefix as before."""
    monkeypatch.setattr(os, "name", "nt")
    long_path = str(tmp_path / ("a" * 300))
    extended = extend_path(long_path)
    assert extended.startswith("\\\\?\\")


def test_extend_path_short_windows_path_no_prefix(monkeypatch, tmp_path):
    monkeypatch.setattr(os, "name", "nt")
    short_path = str(tmp_path / "hosts")
    extended = extend_path(short_path)
    assert not extended.startswith("\\\\?\\")


if __name__ == "__main__":
    print("run via pytest: monkeypatch fixture is required")
