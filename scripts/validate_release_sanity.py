#!/usr/bin/env python3
"""Offline validation for the 12-case release-sanity dataset."""

from __future__ import annotations

import json
import sys

from teachintent.release_sanity import validate_release_sanity_dataset


def main() -> int:
    report = validate_release_sanity_dataset()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 2


if __name__ == "__main__":
    sys.exit(main())

