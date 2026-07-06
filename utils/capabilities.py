"""
capabilities.yaml loader — the source-of-truth artifact catalog.

Extracts the category keys (`option.value`) per OS capability and provides the
set used to validate the collector registry against the catalog at startup.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict, List, Set

import yaml

_OS_BY_CAP = {"collect_windows": "windows", "collect_linux": "linux", "collect_macos": "macos"}


def capabilities_path() -> str:
    import sys

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and os.path.exists(os.path.join(meipass, "capabilities.yaml")):
        return os.path.join(meipass, "capabilities.yaml")
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "capabilities.yaml")


@lru_cache(maxsize=1)
def load() -> dict:
    with open(capabilities_path(), "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def category_keys(os_name: str = "") -> Set[str]:
    """All category `option.value`s, optionally filtered to one OS."""
    keys: Set[str] = set()
    for cap in load().get("capabilities", []):
        cap_os = _OS_BY_CAP.get(cap.get("id", ""), "")
        if os_name and cap_os != os_name:
            continue
        for inp in cap.get("inputs", []):
            if inp.get("name") == "categories":
                for opt in inp.get("options", []) or []:
                    keys.add(opt["value"])
    return keys


def keys_by_os() -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for cap in load().get("capabilities", []):
        cap_os = _OS_BY_CAP.get(cap.get("id", ""), cap.get("id", ""))
        vals = []
        for inp in cap.get("inputs", []):
            if inp.get("name") == "categories":
                vals = [o["value"] for o in (inp.get("options") or [])]
        result[cap_os] = vals
    return result
