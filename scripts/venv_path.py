#!/usr/bin/env python3
"""Compute (and optionally create) the hash-bucketed shared venv.

The hash is sha256(pyproject.toml || uv.lock)[:16]. Two worktrees with
identical dependency specifications share the same venv; different
specifications get isolated buckets.

Usage:
    python scripts/venv_path.py [--root PATH] [--create]

    --root PATH   Project root to hash against (default: current directory)
    --create      Create the venv if it does not exist

Exit codes:
    0 - success (path printed to stdout)
    1 - pyproject.toml or uv.lock missing (cannot use shared venv)
    2 - uv sync failed during --create
"""
import argparse
import hashlib
import os
import pathlib
import shutil
import subprocess
import sys


def compute_hash(root: pathlib.Path) -> str:
    h = hashlib.sha256()
    for name in ('pyproject.toml', 'uv.lock'):
        p = root / name
        if not p.exists():
            raise FileNotFoundError(name)
        h.update(name.encode('utf-8'))
        h.update(b'\x00')
        h.update(p.read_bytes())
        h.update(b'\x00')
    return h.hexdigest()[:16]


def bucket_path(root: pathlib.Path, digest: str) -> pathlib.Path:
    return root / '.pi-agent' / 'venvs' / digest


def main() -> int:
    parser = argparse.ArgumentParser(description='Shared venv path utility')
    parser.add_argument('--root', default='.', help='Project root (default: cwd)')
    parser.add_argument('--create', action='store_true', help='Create venv if absent')
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    try:
        digest = compute_hash(root)
    except FileNotFoundError as e:
        print(f"ERROR: {e} not found in {root}", file=sys.stderr)
        print("Cannot use shared venv; fall back to per-worktree uv sync.", file=sys.stderr)
        return 1

    bucket = bucket_path(root, digest)

    if args.create:
        bucket.parent.mkdir(parents=True, exist_ok=True)
        if bucket.exists():
            print(str(bucket))
            return 0
        env = {**os.environ, 'UV_PROJECT_ENVIRONMENT': str(bucket)}
        try:
            subprocess.run(
                ['uv', 'sync', '--frozen', '--no-install-project'],
                check=True,
                env=env,
                cwd=str(root),
            )
        except subprocess.CalledProcessError as e:
            print(f"ERROR: uv sync failed with exit code {e.returncode}", file=sys.stderr)
            # Remove partial bucket to keep state clean
            if bucket.exists():
                shutil.rmtree(bucket, ignore_errors=True)
            return 2

    print(str(bucket))
    return 0


if __name__ == '__main__':
    sys.exit(main())