"""Safely sweep abandoned/retired staged document uploads.

Usage from the backend directory:

    python3 scripts/cleanup_pending_documents.py
    python3 scripts/cleanup_pending_documents.py --apply
    python3 scripts/cleanup_pending_documents.py --apply --batch-size 500

The default is a dry run.  ``--apply`` is required for DB/file mutation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.document_lifecycle import (  # noqa: E402
    PENDING_DOCUMENT_TTL_HOURS,
    cleanup_expired_pending_documents,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean expired and retired pending document uploads."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag the command is read-only.",
    )
    parser.add_argument(
        "--ttl-hours",
        type=int,
        default=PENDING_DOCUMENT_TTL_HOURS,
        help="TTL for abandoned staged/review documents.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Maximum rows considered per lifecycle category.",
    )
    args = parser.parse_args()

    result = cleanup_expired_pending_documents(
        ttl_hours=max(1, args.ttl_hours),
        batch_size=max(1, args.batch_size),
        dry_run=not args.apply,
    )

    print(json.dumps(result, indent=2, sort_keys=True))

    if not args.apply:
        print("Dry run only. Re-run with --apply to perform cleanup.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
