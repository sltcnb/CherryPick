"""
Raw block-device source with BitLocker unlock (dead-box on Linux).

Ports Talon's ExternalDiskCollector mount lifecycle: BitLocker detection
(``-FVE-FS-`` signature), unlock via dislocker-fuse → cryptsetup fallback, then a
read-only ntfs-3g mount. Once mounted, all primitives delegate to a
:class:`~sources.live.MountedVolumeSource` over the mount point.

    apt-get install dislocker cryptsetup ntfs-3g
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from sources.base import Source
from sources.live import MountedVolumeSource

logger = logging.getLogger(__name__)

IS_LINUX = os.name == "posix" and os.uname().sysname == "Linux" if hasattr(os, "uname") else False


class RawDeviceSource(Source):
    """Unlock (if needed) and mount a raw NTFS device, then serve artifacts."""

    sequential = True  # dead-box against a single device: keep IO ordered

    def __init__(self, disk: str, bitlocker_key: str = ""):
        self.disk = disk
        self.bitlocker_key = (bitlocker_key or "").strip()
        self._dislocker_dir: Optional[Path] = None
        self._ntfs_dir: Optional[Path] = None
        self._cryptsetup_map: Optional[str] = None
        self._delegate: Optional[MountedVolumeSource] = None

    # ── lifecycle ────────────────────────────────────────────────────────────
    def open(self) -> "RawDeviceSource":
        root = self._unlock_and_mount()
        if root is None:
            raise RuntimeError(f"failed to unlock/mount device {self.disk}")
        self._delegate = MountedVolumeSource(str(root))
        return self

    def close(self) -> None:
        if self._ntfs_dir and self._ntfs_dir.exists():
            self._umount(self._ntfs_dir)
            try:
                self._ntfs_dir.rmdir()
            except OSError:
                pass
        if self._dislocker_dir and self._dislocker_dir.exists():
            self._umount(self._dislocker_dir)
            try:
                self._dislocker_dir.rmdir()
            except OSError:
                pass
        if self._cryptsetup_map:
            cs = shutil.which("cryptsetup")
            if cs:
                subprocess.run(["sudo", cs, "close", self._cryptsetup_map],
                               capture_output=True, timeout=30)
            self._cryptsetup_map = None

    # ── mount lifecycle (ported from Talon ExternalDiskCollector) ─────────────
    def _run_privileged(self, cmd: list, timeout: int = 60) -> bool:
        if IS_LINUX and os.getuid() != 0:
            cmd = ["sudo"] + cmd
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=timeout)
            if r.returncode != 0:
                err = (r.stderr or r.stdout or b"").decode(errors="replace")[:300]
                logger.warning("%s failed: %s", cmd[0], err)
                return False
            return True
        except Exception as exc:
            logger.warning("%s error: %s", cmd[0], exc)
            return False

    def _detect_bitlocker(self, device: str) -> bool:
        try:
            with open(device, "rb") as fh:
                header = fh.read(16)
            return header[3:11] == b"-FVE-FS-"
        except (PermissionError, OSError):
            return bool(self.bitlocker_key)

    def _unlock_bitlocker(self, device: str, mount_point: Path) -> Optional[str]:
        mount_point.mkdir(parents=True, exist_ok=True)
        dl_bin = shutil.which("dislocker-fuse") or shutil.which("dislocker")
        if dl_bin:
            dl_help = ""
            try:
                r = subprocess.run([dl_bin, "--help"], capture_output=True, text=True, timeout=5)
                dl_help = r.stderr + r.stdout
            except Exception:
                pass
            cmd = [dl_bin, "-V", device] if "-V" in dl_help else [dl_bin, device]
            if self.bitlocker_key:
                if re.match(r"^[\d\-]+$", self.bitlocker_key):
                    cmd += ["-p", self.bitlocker_key]
                else:
                    cmd += ["-u", self.bitlocker_key]
            cmd += ["--", str(mount_point)]
            logger.info("dislocker-fuse: unlocking %s -> %s", device, mount_point)
            if self._run_privileged(cmd, timeout=120):
                dl_file = mount_point / "dislocker-file"
                if dl_file.exists():
                    return str(dl_file)
                logger.warning("dislocker succeeded but dislocker-file absent")
            else:
                logger.info("dislocker-fuse failed — trying cryptsetup fallback")

        cs = shutil.which("cryptsetup")
        if not cs:
            logger.warning("neither dislocker-fuse nor cryptsetup found "
                           "(apt-get install dislocker cryptsetup)")
            return None
        if not self.bitlocker_key:
            logger.warning("no BitLocker key supplied — cryptsetup requires one for BITLK")
            return None

        map_name = f"fh_bitlk_{os.path.basename(device).replace('/', '_')}"
        mapper_path = f"/dev/mapper/{map_name}"
        if Path(mapper_path).exists():
            subprocess.run(["sudo", cs, "close", map_name], capture_output=True, timeout=15)

        key_with_dash = self.bitlocker_key
        key_without_dash = re.sub(r"[-\s]", "", key_with_dash)

        def _try_cs(key: str, label: str) -> subprocess.CompletedProcess:
            shell_cmd = (
                f"{shlex.quote(cs)} open --type bitlk --verbose "
                f"--key-file <(printf '%s' {shlex.quote(key)}) "
                f"{shlex.quote(device)} {shlex.quote(map_name)}"
            )
            r = subprocess.run(["sudo", "bash", "-c", shell_cmd],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            out = (r.stderr + r.stdout).decode(errors="replace").strip()
            logger.info("cryptsetup [%s]: rc=%s out=%r", label, r.returncode, out)
            return r

        try:
            proc = _try_cs(key_with_dash, "with-dashes")
            if proc.returncode != 0 and key_without_dash != key_with_dash:
                proc = _try_cs(key_without_dash, "no-dashes")
            if proc.returncode != 0:
                logger.warning("cryptsetup bitlk failed")
                return None
        except Exception as exc:
            logger.warning("cryptsetup error: %s", exc)
            return None

        if not Path(mapper_path).exists():
            logger.warning("cryptsetup succeeded but %s not found", mapper_path)
            return None
        self._cryptsetup_map = map_name
        return mapper_path

    def _mount_ntfs(self, source: str, mount_point: Path) -> bool:
        mount_point.mkdir(parents=True, exist_ok=True)
        ntfs3g = shutil.which("ntfs-3g") or shutil.which("mount.ntfs-3g")
        if ntfs3g and self._run_privileged(
            [ntfs3g, source, str(mount_point), "-o",
             "ro,noatime,streams_interface=none,nodev,nosuid"], timeout=30):
            return True
        return self._run_privileged(
            ["mount", "-t", "ntfs", "-o", "ro,noatime", source, str(mount_point)], timeout=30)

    def _umount(self, path: Path) -> None:
        self._run_privileged(["umount", "-l", str(path)], timeout=30)

    def _unlock_and_mount(self) -> Optional[Path]:
        disk_path = Path(self.disk)
        if disk_path.is_dir():
            logger.info("using existing mount: %s", disk_path)
            return disk_path
        device = str(disk_path)
        if self.bitlocker_key or self._detect_bitlocker(device):
            logger.info("BitLocker volume — unlocking %s", device)
            self._dislocker_dir = Path(tempfile.mkdtemp(prefix="fh_dislocker_"))
            dl_file = self._unlock_bitlocker(device, self._dislocker_dir)
            if dl_file is None:
                return None
            ntfs_source = dl_file
        else:
            ntfs_source = device
        self._ntfs_dir = Path(tempfile.mkdtemp(prefix="fh_ntfs_"))
        if not self._mount_ntfs(ntfs_source, self._ntfs_dir):
            logger.warning("failed to mount NTFS from %s", ntfs_source)
            return None
        return self._ntfs_dir

    # ── delegated primitives ─────────────────────────────────────────────────
    def _d(self) -> MountedVolumeSource:
        if self._delegate is None:
            raise RuntimeError("RawDeviceSource.open() must be called before use")
        return self._delegate

    def expand(self, path: str) -> str:
        return self._d().expand(path)

    def exists(self, path: str) -> bool:
        return self._d().exists(path)

    def is_file(self, path: str) -> bool:
        return self._d().is_file(path)

    def list_dir(self, path: str) -> List[str]:
        return self._d().list_dir(path)

    def file_size(self, path: str) -> int:
        return self._d().file_size(path)

    def extract(self, src_path: str, dest_path: str) -> Tuple[bool, Optional[str]]:
        return self._d().extract(src_path, dest_path)

    def roots(self) -> List[str]:
        return self._d().roots()
