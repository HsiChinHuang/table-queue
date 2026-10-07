#!/usr/bin/env python3
"""List or delete stale hash-bucketed venvs.

Usage:
    python scripts/venv_cleanup.py [--root PATH] [--days N] [--delete]

    --root PATH   Project root (default: cwd)
    --days N      Stale threshold in days. If omitted, reads
                  `venv.cleanup_after_days` from docs/config.yaml;
                  falls back to 30 if the config is missing.
    --delete      Actually delete stale buckets (default: list only)

Exit codes:
    0 - success
    1 - venvs directory not found
"""
import argparse
import pathlib
import re
import shutil
import sys
import time


DEFAULT_DAYS = 30


def load_config_days(root: pathlib.Path) -> int | None:
    """Read venv.cleanup_after_days from docs/config.yaml without a YAML parser.

    The config format is simple enough that a line scan is sufficient.
    Lines under `venv:` (indented) are checked for `cleanup_after_days: N`.
    Returns None if the key is missing or unreadable.
    """
    config_path = root / 'docs' / 'config.yaml'
    if not config_path.exists():
        return None
    try:
        text = config_path.read_text(encoding='utf-8')
    except OSError as e:
        print(f"WARN: cannot read {config_path}: {e}", file=sys.stderr)
        return None

    in_venv = False
    for line in text.splitlines():
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith('#'):
            continue
        # Top-level key (no leading whitespace)
        if not line.startswith((' ', '\t')):
            in_venv = stripped.startswith('venv:')
            continue
        if in_venv:
            m = re.match(r'\s+cleanup_after_days:\s*(\d+)\s*$', stripped)
            if m:
                value = int(m.group(1))
                return value if value > 0 else None
    return None


def find_stale(bucket_root: pathlib.Path, days: int):
    if not bucket_root.is_dir():
        return []
    cutoff = time.time() - days * 86400
    stale = []
    for child in bucket_root.iterdir():
        if not child.is_dir():
            continue
        mtime = child.stat().st_mtime
        if mtime < cutoff:
            stale.append((child, mtime))
    return sorted(stale, key=lambda x: x[1])


def main() -> int:
    parser = argparse.ArgumentParser(description='Stale venv cleanup')
    parser.add_argument('--root', default='.', help='Project root (default: cwd)')
    parser.add_argument(
        '--days',
        type=int,
        default=None,
        help='Stale threshold in days (default: read from config, else 30)',
    )
    parser.add_argument('--delete', action='store_true', help='Delete stale buckets')
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    bucket_root = root / '.pi-agent' / 'venvs'

    # 1. Determine days first, so the threshold is always printed
    if args.days is not None:
        days = args.days
        source = 'cli'
    else:
        config_days = load_config_days(root)
        if config_days is not None:
            days = config_days
            source = 'config'
        else:
            days = DEFAULT_DAYS
            source = 'default'

    print(f"Stale threshold: {days} days (source: {source})")

    # 2. Then check the directory
    if not bucket_root.is_dir():
        print(f"No venv directory at {bucket_root}", file=sys.stderr)
        return 1

    stale = find_stale(bucket_root, days)
    if not stale:
        print(f"No buckets older than {days} days")
        return 0

    for path, mtime in stale:
        age_days = (time.time() - mtime) / 86400
        print(f"{path}  ({age_days:.1f} days old)")
        if args.delete:
            shutil.rmtree(path, ignore_errors=True)

    if args.delete:
        print(f"Deleted {len(stale)} bucket(s)")
    else:
        print(f"Found {len(stale)} stale bucket(s). Re-run with --delete to remove.")
    return 0


if __name__ == '__main__':
    sys.exit(main())