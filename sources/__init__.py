"""
Unified source abstraction for ForensicHarvester.

A :class:`Source` presents the same primitive filesystem operations regardless of
whether artifacts come from a live host, a mounted volume, a pytsk3 disk image
(E01/dd/vhd), or a raw block device (optionally BitLocker-encrypted). Collectors
call these primitives (via ``BaseCollector``) and are therefore source-agnostic.

Factory
-------
:func:`build_source` picks the right implementation from the run parameters:

    build_source(source_root=..., image=DiskImage(...))   # pytsk3 image
    build_source(source_root="/mnt/win")                  # live / mounted dir
    build_source(disk="/dev/sdb1", bitlocker_key="...")   # raw device
"""

from __future__ import annotations

from typing import Any, Optional

from sources.base import Source
from sources.live import LiveFilesystemSource, MountedVolumeSource
from sources.image import ImageSource
from sources.rawdevice import RawDeviceSource

__all__ = [
    "Source",
    "LiveFilesystemSource",
    "MountedVolumeSource",
    "ImageSource",
    "RawDeviceSource",
    "build_source",
]


def build_source(
    source_root: Optional[str] = None,
    *,
    image: Any = None,
    mount_path: Optional[str] = None,
    disk: Optional[str] = None,
    bitlocker_key: str = "",
) -> Source:
    """Construct the appropriate :class:`Source` for the given inputs."""
    if disk:
        return RawDeviceSource(disk, bitlocker_key=bitlocker_key)
    if image is not None:
        return ImageSource(image)
    if mount_path:
        return MountedVolumeSource(mount_path)
    return LiveFilesystemSource(source_root or "/")
