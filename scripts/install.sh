#!/usr/bin/env sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root (use sudo)." >&2
  exit 1
fi

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE_SCRIPT="$REPO_DIR/zfs_autosnapshot.py"
TEMPLATE_FILE="$REPO_DIR/cron/zfs-autosnapshot.cron"

INSTALL_BIN=${INSTALL_BIN:-/usr/local/sbin/zfs-autosnapshot}
CRON_FILE=${CRON_FILE:-/etc/cron.d/zfs-autosnapshot}
PYTHON_BIN=${PYTHON_BIN:-$(command -v python3)}

if [ ! -f "$SOURCE_SCRIPT" ]; then
  echo "Missing source file: $SOURCE_SCRIPT" >&2
  exit 1
fi

if [ ! -f "$TEMPLATE_FILE" ]; then
  echo "Missing cron template: $TEMPLATE_FILE" >&2
  exit 1
fi

if ! command -v zfs >/dev/null 2>&1; then
  echo "zfs command not found in PATH." >&2
  exit 1
fi

install -m 0755 "$SOURCE_SCRIPT" "$INSTALL_BIN"

TMP_CRON=$(mktemp)
cp "$TEMPLATE_FILE" "$TMP_CRON"

sed -i.bak "s|__PYTHON__|$PYTHON_BIN|g" "$TMP_CRON"
sed -i.bak "s|__SCRIPT__|$INSTALL_BIN|g" "$TMP_CRON"
rm -f "$TMP_CRON.bak"

install -m 0644 "$TMP_CRON" "$CRON_FILE"

rm -f "$TMP_CRON"

echo "Installed executable: $INSTALL_BIN"
echo "Installed cron file:  $CRON_FILE"
echo "Validate with: crontab -l 2>/dev/null || true; cat $CRON_FILE"
