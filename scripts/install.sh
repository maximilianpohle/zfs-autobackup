#!/usr/bin/env sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run as root (use sudo)." >&2
  exit 1
fi

INSTALL_BIN=${INSTALL_BIN:-/usr/local/sbin/zfs-autosnapshot}
CRON_FILE=${CRON_FILE:-/etc/cron.d/zfs-autosnapshot}
PYTHON_BIN=${PYTHON_BIN:-$(command -v python3)}
APT_CONFLICT_PACKAGE=${APT_CONFLICT_PACKAGE:-zfs-auto-snapshot}
RAW_BASE_URL=${RAW_BASE_URL:-https://raw.githubusercontent.com/maximilianpohle/zfs-autobackup/main}
SCRIPT_RAW_URL=${SCRIPT_RAW_URL:-$RAW_BASE_URL/zfs_autosnapshot.py}
CRON_TEMPLATE_RAW_URL=${CRON_TEMPLATE_RAW_URL:-$RAW_BASE_URL/cron/zfs-autosnapshot.cron}

download_file() {
  url=$1
  out=$2

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$out"
    return 0
  fi

  if command -v wget >/dev/null 2>&1; then
    wget -qO "$out" "$url"
    return 0
  fi

  echo "Neither curl nor wget is available for downloading files." >&2
  return 1
}

ensure_apt_package_absent() {
  pkg=$1

  if ! command -v apt-get >/dev/null 2>&1; then
    return 0
  fi

  if dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
    echo "Conflicting apt package is installed: $pkg" >&2
    echo "Please remove it first, then run the installer again." >&2
    exit 1
  fi
}

ensure_apt_package_absent "$APT_CONFLICT_PACKAGE"

if ! command -v zfs >/dev/null 2>&1; then
  echo "zfs command not found in PATH." >&2
  exit 1
fi

TMP_SCRIPT=$(mktemp)
TMP_CRON=$(mktemp)

cleanup() {
  rm -f "$TMP_SCRIPT" "$TMP_CRON" "$TMP_CRON.bak"
}
trap cleanup EXIT INT TERM

download_file "$SCRIPT_RAW_URL" "$TMP_SCRIPT"
download_file "$CRON_TEMPLATE_RAW_URL" "$TMP_CRON"

install -m 0755 "$TMP_SCRIPT" "$INSTALL_BIN"

sed -i.bak "s|__PYTHON__|$PYTHON_BIN|g" "$TMP_CRON"
sed -i.bak "s|__SCRIPT__|$INSTALL_BIN|g" "$TMP_CRON"
rm -f "$TMP_CRON.bak"

install -m 0644 "$TMP_CRON" "$CRON_FILE"

echo "Installed executable: $INSTALL_BIN"
echo "Installed cron file:  $CRON_FILE"
echo "Script source:         $SCRIPT_RAW_URL"
echo "Cron template source:  $CRON_TEMPLATE_RAW_URL"
echo "Checked apt conflict:  $APT_CONFLICT_PACKAGE (absent)"
echo "Validate with: crontab -l 2>/dev/null || true; cat $CRON_FILE"
