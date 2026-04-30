# zfs-autosnapshot (Python)

A small zfs-auto-snapshot alternative controlled via dataset properties.

This repository is Cron-first by design because installation is usually faster and simpler than setting up multiple systemd units.

Snapshot naming uses the exact current timestamp for every run (no interval-based rounding).

Supported intervals:
- monthly
- weekly
- daily
- frequently

## Installation

Requirements:
- Python 3
- zfs command available in PATH
- root privileges for zfs snapshot and zfs destroy

### Option 1: Clone and install

```bash
git clone https://github.com/<owner>/<repo>.git
cd <repo>
sudo sh scripts/install.sh
```

### Option 2: Raw one-liner installer (no clone)

```bash
curl -fsSL https://raw.githubusercontent.com/maximilianpohle/zfs-autobackup/main/scripts/install.sh | sudo sh
```

Alternative with `wget`:

```bash
wget -qO- https://raw.githubusercontent.com/maximilianpohle/zfs-autobackup/main/scripts/install.sh | sudo sh
```

The installer does the following:
- installs the executable to /usr/local/sbin/zfs-autosnapshot
- installs Cron schedule file to /etc/cron.d/zfs-autosnapshot
- downloads script and cron template from GitHub RAW URLs
- on apt-based systems, aborts if conflicting package zfs-auto-snapshot is installed

Optional override variables for custom branch/repo:

```bash
curl -fsSL https://raw.githubusercontent.com/maximilianpohle/zfs-autobackup/main/scripts/install.sh | \
	sudo RAW_BASE_URL="https://raw.githubusercontent.com/maximilianpohle/zfs-autobackup/main" sh
```

Optional override for apt conflict package name:

```bash
curl -fsSL https://raw.githubusercontent.com/maximilianpohle/zfs-autobackup/main/scripts/install.sh | \
	sudo APT_CONFLICT_PACKAGE="zfs-auto-snapshot" sh
```

## Cron schedule

Installed Cron file:
- /etc/cron.d/zfs-autosnapshot

Default schedule:

```cron
*/15 * * * * root /usr/bin/python3 /usr/local/sbin/zfs-autosnapshot frequently
10 0 * * * root /usr/bin/python3 /usr/local/sbin/zfs-autosnapshot daily
20 0 * * 1 root /usr/bin/python3 /usr/local/sbin/zfs-autosnapshot weekly
30 0 1 * * root /usr/bin/python3 /usr/local/sbin/zfs-autosnapshot monthly
```

To customize timing, edit /etc/cron.d/zfs-autosnapshot and reload cron if needed by your distribution.

## Usage

```bash
python3 zfs_autosnapshot.py monthly
python3 zfs_autosnapshot.py weekly
python3 zfs_autosnapshot.py daily
python3 zfs_autosnapshot.py frequently
```

Process only specific root datasets:

```bash
python3 zfs_autosnapshot.py daily tank/data tank/backups
```

Dry run:

```bash
python3 zfs_autosnapshot.py daily --dry-run
```

## Dataset properties

Enable per interval:
- com.zfsautosnap:monthly=on|off
- com.zfsautosnap:weekly=on|off
- com.zfsautosnap:daily=on|off
- com.zfsautosnap:frequently=on|off

Retention per interval:
- com.zfsautosnap:keep-monthly=<number>
- com.zfsautosnap:keep-weekly=<number>
- com.zfsautosnap:keep-daily=<number>
- com.zfsautosnap:keep-frequently=<number>

Optional recursive mode (inheritable):
- com.zfsautosnap:recursive=on|off

Default retention when keep-* is not set:
- keep-monthly=12
- keep-weekly=8
- keep-daily=31
- keep-frequently=96

Example property setup:

```bash
zfs set com.zfsautosnap:daily=on tank/data
zfs set com.zfsautosnap:keep-daily=14 tank/data

zfs set com.zfsautosnap:weekly=on tank/data
zfs set com.zfsautosnap:keep-weekly=8 tank/data

zfs set com.zfsautosnap:monthly=on tank/data
zfs set com.zfsautosnap:keep-monthly=12 tank/data

zfs set com.zfsautosnap:frequently=on tank/data
zfs set com.zfsautosnap:keep-frequently=96 tank/data

# Enable recursion on parent (applies to children via inheritance)
zfs set com.zfsautosnap:recursive=on tank/data
```

## Logging

The script writes action and error logs to syslog.

Examples:

```bash
journalctl -t zfs-autosnapshot -f
tail -f /var/log/syslog | grep zfs-autosnapshot
```
