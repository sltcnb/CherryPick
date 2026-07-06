"""
macOS artifact collectors (ported from Talon MacOSCollector).

One class per capability key (``macos_*``). Source-relative paths; per-user
artifacts are swept under ``Users/<name>``. Registered automatically.
"""

import logging
from datetime import datetime

from collectors.base import BaseCollector, CollectionResult

logger = logging.getLogger(__name__)


class _MacBase(BaseCollector):
    PATHS: list = []
    DEST = ''
    USER_FILES: list = []
    USER_DIRS: list = []

    def _get_time(self):
        return datetime.now()

    def _users(self):
        users = []
        if self._path_exists('var/root'):
            users.append('var/root')
        for entry in self._list_dir('Users'):
            if entry in ('.', '..', 'Shared'):
                continue
            users.append(f"Users/{entry}")
        return users

    def collect(self) -> CollectionResult:
        self.result.start_time = self._get_time()
        self._ensure_output_dir()
        n = self._collect_relpaths(self.PATHS, self.DEST)
        for user in self._users():
            uname = user.rstrip('/').split('/')[-1]
            for rel in self.USER_FILES:
                p = f"{user}/{rel}"
                if self._path_exists(p) and self._is_file(p):
                    self._collect_file(p, f"{self.DEST}/{uname}" if self.DEST else uname,
                                       rel.replace('/', '_'))
            for d in self.USER_DIRS:
                n += self._collect_relpaths([f"{user}/{d}"],
                                            f"{self.DEST}/{uname}" if self.DEST else uname)
        logger.info("%s: collected %d", self.category, n)
        self.result.end_time = self._get_time()
        return self.result


class MacLogsCollector(_MacBase):
    category = 'macos_logs'
    DEST = 'logs'
    PATHS = ['var/log/system.log', 'var/log/install.log', 'var/log/fsck_apfs.log',
             'var/log/wifi.log', 'var/log/DiagnosticMessages']


class MacShellHistoryCollector(_MacBase):
    category = 'macos_shell_history'
    DEST = 'history'
    USER_FILES = ['.bash_history', '.zsh_history', '.sh_history', '.python_history']


class MacConfigCollector(_MacBase):
    category = 'macos_config'
    DEST = 'config'
    PATHS = [
        'etc/passwd', 'etc/group', 'etc/hosts', 'etc/resolv.conf',
        'etc/ssh/sshd_config', 'private/etc/sudoers', 'private/etc/sudoers.d',
        'System/Library/CoreServices/SystemVersion.plist', 'etc/sudoers.d',
    ]


class MacLaunchAgentsCollector(_MacBase):
    category = 'macos_launch_agents'
    DEST = 'launchagents'
    PATHS = [
        'Library/LaunchAgents', 'Library/LaunchDaemons',
        'System/Library/LaunchAgents', 'System/Library/LaunchDaemons',
    ]
    USER_DIRS = ['Library/LaunchAgents']


class MacBrowserCollector(_MacBase):
    category = 'macos_browser'
    DEST = 'browser'
    USER_FILES = [
        'Library/Safari/History.db', 'Library/Safari/Downloads.plist',
        'Library/Safari/Bookmarks.plist',
        'Library/Application Support/Google/Chrome/Default/History',
        'Library/Application Support/Firefox/profiles.ini',
    ]


class MacPlistCollector(_MacBase):
    category = 'macos_plist'
    DEST = 'plist'
    PATHS = ['Library/Preferences/com.apple.loginwindow.plist',
             'Library/Preferences/SystemConfiguration']
    USER_DIRS = ['Library/Preferences']


class MacTriageCollector(_MacBase):
    category = 'macos_triage'
    DEST = 'triage'
    USER_FILES = [
        'Library/Application Support/com.apple.TCC/TCC.db',
        'Library/Preferences/com.apple.recentitems.plist',
    ]
    PATHS = ['Library/Application Support/com.apple.TCC/TCC.db',
             'var/db/dslocal/nodes/Default/users']
