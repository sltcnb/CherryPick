"""Registry <-> capabilities.yaml consistency (catches dispatch drift)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collectors import collector_registry as reg  # noqa: E402
from utils import capabilities as caps  # noqa: E402


def test_no_drift_between_registry_and_capabilities():
    problems = reg.validate_against_capabilities(caps.category_keys())
    assert problems == [], f"registry/capabilities drift: {problems}"


def test_every_capability_key_resolves():
    for key in caps.category_keys():
        assert reg.get(key) is not None, f"no collector for capability key {key!r}"


def test_aliases_resolve():
    for alias, native in reg.CANONICAL_ALIASES.items():
        cls = reg.get(alias)
        assert cls is not None, f"alias {alias!r} did not resolve"
        assert reg.get(native) is cls, f"alias {alias!r} != native {native!r}"


def test_expected_collector_count():
    keys = reg.all_keys()
    # 52 Windows + 11 Linux + 7 macOS
    assert len(keys) == 70, f"expected 70 collectors, got {len(keys)}"


if __name__ == "__main__":
    test_no_drift_between_registry_and_capabilities()
    test_every_capability_key_resolves()
    test_aliases_resolve()
    test_expected_collector_count()
    print("PASS registry consistency")
