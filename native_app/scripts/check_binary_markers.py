from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that a built binary contains expected markers.")
    parser.add_argument("binary", help="Path to executable/binary")
    parser.add_argument("markers", nargs="+", help="ASCII markers that must be present")
    args = parser.parse_args()

    binary_path = Path(args.binary).resolve()
    payload = binary_path.read_bytes()

    missing = [marker for marker in args.markers if marker.encode("utf-8") not in payload]
    if missing:
        raise SystemExit(
            f"Binary {binary_path} is missing expected markers: {', '.join(missing)}"
        )

    print(f"Binary markers OK: {binary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
