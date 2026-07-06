"""
Linux artifact collectors (ported from Talon LinuxCollector).

One class per capability key (``linux_*``). Paths are source-relative so they work
against a live host (source root ``/``), a mounted image, or a pytsk3 image.
Registered automatically by the collector registry.
"""

import logging
from datetime import datetime

from collectors.base import BaseCollector, CollectionResult

logger = logging.getLogger(__name__)


class _LinuxBase(BaseCollector):
    PATHS: list = []
    DEST = ''

    def _get_time(self):
        return datetime.now()

    def collect(self) -> CollectionResult:
        self.result.start_time = self._get_time()
        self._ensure_output_dir()
        n = self._collect_relpaths(self.PATHS, self.DEST)
        # Also sweep per-user home artifacts if HOME_GLOBS defined.
        for user in self._home_dirs():
            for rel in getattr(self, 'HOME_FILES', []):
                p = f"{user}/{rel}"
                if self._path_exists(p) and self._is_file(p):
                    uname = user.rstrip('/').split('/')[-1]
                    self._collect_file(p, f"{self.DEST}/{uname}" if self.DEST else uname,
                                       rel.replace('/', '_'))
        logger.info("%s: collected %d", self.category, n)
        self.result.end_time = self._get_time()
        return self.result

    def _home_dirs(self):
        homes = []
        if self._path_exists('root'):
            homes.append('root')
        for entry in self._list_dir('home'):
            if entry not in ('.', '..'):
                homes.append(f"home/{entry}")
        return homes


class LinuxLogsCollector(_LinuxBase):
    category = 'linux_logs'
    DEST = 'logs'
    PATHS = [
        'var/log/auth.log', 'var/log/syslog', 'var/log/messages', 'var/log/secure',
        'var/log/kern.log', 'var/log/daemon.log', 'var/log/audit/audit.log',
        'var/log/dpkg.log', 'var/log/apt/history.log', 'var/log/wtmp', 'var/log/btmp',
        'var/log/lastlog', 'var/log/faillog', 'var/run/utmp', 'var/log/apache2',
        'var/log/nginx',
    ]


class LinuxConfigCollector(_LinuxBase):
    category = 'linux_config'
    DEST = 'config'
    PATHS = [
        'etc/passwd', 'etc/group', 'etc/shadow', 'etc/gshadow', 'etc/sudoers',
        'etc/hostname', 'etc/hosts', 'etc/resolv.conf', 'etc/nsswitch.conf',
        'etc/os-release', 'etc/issue', 'etc/motd', 'etc/crontab', 'etc/ssh/sshd_config',
        'etc/profile', 'etc/environment', 'etc/sysctl.conf', 'etc/ld.so.conf',
        'etc/fstab', 'etc/security/limits.conf', 'etc/login.defs', 'etc/sudoers.d',
        'etc/pam.d', 'etc/modules-load.d', 'etc/modprobe.d', 'etc/sysctl.d',
    ]


class LinuxShellHistoryCollector(_LinuxBase):
    category = 'linux_shell_history'
    DEST = 'history'
    HOME_FILES = ['.bash_history', '.zsh_history', '.sh_history',
                  '.python_history', '.mysql_history']


class LinuxCronCollector(_LinuxBase):
    category = 'linux_cron'
    DEST = 'cron'
    PATHS = [
        'etc/cron.d', 'etc/cron.hourly', 'etc/cron.daily', 'etc/cron.weekly',
        'etc/cron.monthly', 'var/spool/cron/crontabs', 'var/spool/cron',
    ]


class LinuxSSHCollector(_LinuxBase):
    category = 'linux_ssh'
    DEST = 'ssh'
    HOME_FILES = ['.ssh/authorized_keys', '.ssh/known_hosts', '.ssh/config',
                  '.ssh/id_rsa.pub', '.ssh/id_ed25519.pub', '.ssh/id_ecdsa.pub']


class LinuxPersistenceCollector(_LinuxBase):
    category = 'linux_persistence'
    DEST = 'persistence'
    PATHS = [
        'etc/systemd/system', 'usr/lib/systemd/system', 'lib/systemd/system',
        'etc/init.d', 'etc/rc.local', 'etc/xdg/autostart', 'etc/systemd/user',
    ]
    HOME_FILES = ['.config/autostart', '.bashrc', '.bash_profile', '.profile']


class LinuxNetworkConfigCollector(_LinuxBase):
    category = 'linux_network'
    DEST = 'network'
    PATHS = [
        'etc/network/interfaces', 'etc/netplan', 'etc/NetworkManager/system-connections',
        'etc/iptables', 'etc/hosts.allow', 'etc/hosts.deny', 'proc/net/tcp',
        'proc/net/udp', 'proc/net/arp',
    ]


class LinuxAuditCollector(_LinuxBase):
    category = 'linux_audit'
    DEST = 'audit'
    PATHS = ['etc/audit/auditd.conf', 'etc/audit/audit.rules', 'etc/audit/rules.d',
             'var/log/audit']


class LinuxPackagesCollector(_LinuxBase):
    category = 'linux_packages'
    DEST = 'packages'
    PATHS = [
        'var/lib/dpkg/status', 'var/log/dpkg.log', 'etc/apt/sources.list',
        'etc/apt/sources.list.d', 'var/lib/rpm/Packages', 'etc/yum.repos.d',
    ]


class LinuxContainersCollector(_LinuxBase):
    category = 'linux_containers'
    DEST = 'containers'
    PATHS = [
        'etc/docker/daemon.json', 'var/lib/docker/containers',
        'etc/containerd/config.toml', 'var/lib/kubelet',
    ]


class LinuxUserArtifactsCollector(_LinuxBase):
    category = 'linux_user_artifacts'
    DEST = 'user_artifacts'
    HOME_FILES = [
        '.bashrc', '.bash_profile', '.profile', '.viminfo', '.lesshst',
        '.gitconfig', '.wget-hsts', '.selected_editor', '.config/gtk-3.0/bookmarks',
    ]
