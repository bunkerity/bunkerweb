#!/usr/bin/env python3

import argparse
import logging
from pathlib import Path
from sys import path as sys_path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys_path.insert(0, str(REPOSITORY_ROOT / "src" / "common" / "utils"))

from mmdb import update_bundled_mmdbs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and publish verified DB-IP MMDB files.")
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--temp-root", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    return 0 if update_bundled_mmdbs(args.repo_root / "src" / "bw" / "misc", args.temp_root) else 1


if __name__ == "__main__":
    raise SystemExit(main())
