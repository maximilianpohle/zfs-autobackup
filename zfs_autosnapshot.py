#!/usr/bin/env python3
"""Lightweight zfs-auto-snapshot alternative.

Features:
- Per-dataset activation via ZFS properties for intervals: monthly/weekly/daily/frequent
- Per-dataset retention (how many snapshots to keep per interval)
- Snapshot names use the current timestamp for every run
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import logging.handlers
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable

PREFIX = "com.zfsautosnap"
SUPPORTED_INTERVALS = ("monthly", "weekly", "daily", "hourly", "frequent")
DEFAULT_KEEP = {
    "monthly": 12,
    "weekly": 8,
    "daily": 31,
    "hourly": 8,
    "frequent": 6,
}
LOGGER_NAME = "zfs-autosnapshot"


def setup_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    address = "/dev/log" if os.path.exists("/dev/log") else "/var/run/syslog"
    try:
        handler = logging.handlers.SysLogHandler(address=address)
    except OSError:
        # Fallback to stderr when no syslog socket is available.
        handler = logging.StreamHandler(sys.stderr)

    handler.setFormatter(logging.Formatter(f"{LOGGER_NAME}[%(process)d]: %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


logger = setup_logger()


@dataclass
class DatasetPolicy:
    enabled: bool
    keep: int
    recursive: bool


def run_zfs(args: list[str], check: bool = True) -> str:
    cmd = ["zfs", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"zfs command failed: {' '.join(cmd)}\n{proc.stderr.strip()}")
    return proc.stdout


def list_datasets(roots: list[str] | None = None) -> list[str]:
    args = ["list", "-H", "-o", "name", "-t", "filesystem,volume"]
    if roots:
        for root in roots:
            args.extend(["-r", root])
    output = run_zfs(args)
    return [line.strip() for line in output.splitlines() if line.strip()]


def get_dataset_property(dataset: str, prop: str) -> str:
    output = run_zfs(["get", "-H", "-o", "value", prop, dataset], check=False).strip()
    if not output:
        return "-"
    # zfs get -o value returns one line; for inherited values this is still the value.
    return output.splitlines()[0].strip()


def parse_bool(value: str) -> bool:
    return value.lower() in {"1", "on", "yes", "true"}


def parse_int(value: str, default: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else default
    except ValueError:
        return default


def get_policy(dataset: str, interval: str) -> DatasetPolicy:
    enabled_prop = f"{PREFIX}:{interval}"
    keep_prop = f"{PREFIX}:keep-{interval}"

    enabled_val = get_dataset_property(dataset, enabled_prop)
    keep_val = get_dataset_property(dataset, keep_prop)
    recursive_val = get_dataset_property(dataset, f"{PREFIX}:recursive")

    return DatasetPolicy(
        enabled=parse_bool(enabled_val),
        keep=parse_int(keep_val, DEFAULT_KEEP[interval]),
        recursive=parse_bool(recursive_val),
    )


def period_bucket(interval: str, now: dt.datetime) -> str:
    # Always use the exact current timestamp; no rounding by interval.
    _ = interval
    return now.strftime("%Y-%m-%d-%H%M")


def snapshot_name(interval: str, bucket: str) -> str:
    return f"zfs-auto-snap_{interval}-{bucket}"


def list_dataset_snapshots(dataset: str, interval: str) -> list[str]:
    output = run_zfs([
        "list",
        "-H",
        "-t",
        "snapshot",
        "-o",
        "name",
        "-s",
        "creation",
        "-r",
        dataset,
    ])
    prefix = f"{dataset}@zfs-auto-snap_{interval}-"
    return [line.strip() for line in output.splitlines() if line.startswith(prefix)]


def ensure_snapshot(
    dataset: str,
    interval: str,
    bucket: str,
    recursive: bool = False,
    dry_run: bool = False,
) -> bool:
    snap = f"{dataset}@{snapshot_name(interval, bucket)}"
    existing = list_dataset_snapshots(dataset, interval)
    if snap in existing:
        logger.info("SKIP %s (already exists)", snap)
        return False

    zfs_args = ["snapshot"]
    if recursive:
        zfs_args.append("-r")
    zfs_args.append(snap)

    if dry_run:
        logger.info("DRY zfs %s", " ".join(zfs_args))
        return True

    run_zfs(zfs_args)
    if recursive:
        logger.info("CREATE_RECURSIVE %s", snap)
    else:
        logger.info("CREATE %s", snap)
    return True


def enforce_retention(
    dataset: str,
    interval: str,
    keep: int,
    recursive: bool = False,
    dry_run: bool = False,
) -> int:
    snaps = list_dataset_snapshots(dataset, interval)
    to_delete = snaps[:-keep] if keep > 0 else snaps

    deleted = 0
    for snap in to_delete:
        zfs_args = ["destroy"]
        if recursive:
            zfs_args.append("-r")
        zfs_args.append(snap)

        if dry_run:
            logger.info("DRY zfs %s", " ".join(zfs_args))
            deleted += 1
            continue
        run_zfs(zfs_args)
        if recursive:
            logger.info("DELETE_RECURSIVE %s", snap)
        else:
            logger.info("DELETE %s", snap)
        deleted += 1
    return deleted


def process_dataset(dataset: str, interval: str, now: dt.datetime, dry_run: bool = False) -> tuple[bool, int]:
    policy = get_policy(dataset, interval)
    if not policy.enabled:
        return False, 0

    bucket = period_bucket(interval, now)
    created = ensure_snapshot(
        dataset,
        interval,
        bucket,
        recursive=policy.recursive,
        dry_run=dry_run,
    )
    deleted = enforce_retention(
        dataset,
        interval,
        policy.keep,
        recursive=policy.recursive,
        dry_run=dry_run,
    )
    return created, deleted


def is_descendant_dataset(dataset: str, parents: list[str]) -> bool:
    return any(dataset == parent or dataset.startswith(f"{parent}/") for parent in parents)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Per-dataset ZFS autosnapshot (monthly/weekly/daily/frequent)."
    )
    parser.add_argument("interval", choices=SUPPORTED_INTERVALS, help="Snapshot interval")
    parser.add_argument(
        "datasets",
        nargs="*",
        help="Optional root datasets (default: all datasets)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing anything")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    now = dt.datetime.now()

    try:
        datasets = list_datasets(args.datasets if args.datasets else None)
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 2

    created_count = 0
    deleted_count = 0
    enabled_count = 0
    recursive_roots: list[str] = []

    for dataset in datasets:
        if is_descendant_dataset(dataset, recursive_roots):
            logger.info("SKIP %s (covered by recursive parent)", dataset)
            continue

        try:
            policy = get_policy(dataset, args.interval)
            if not policy.enabled:
                continue

            if policy.recursive:
                recursive_roots.append(dataset)

            created, deleted = process_dataset(dataset, args.interval, now, dry_run=args.dry_run)
        except RuntimeError as exc:
            logger.error("ERROR %s: %s", dataset, exc)
            continue

        enabled_count += 1

        created_count += int(created)
        deleted_count += deleted

    logger.info(
        "DONE interval=%s datasets=%d enabled=%d created=%d deleted=%d dry_run=%s",
        args.interval,
        len(datasets),
        enabled_count,
        created_count,
        deleted_count,
        args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
