"""Run retention from the command line (what `make retention` calls).

    python -m app.jobs.retention                      # dry run, as of today (UTC)
    python -m app.jobs.retention --as-of 2026-12-01   # dry run, as of a date
    python -m app.jobs.retention --apply              # delete, then write reports/<date>.json

Prints the report as JSON. Reads the same configuration as the API (the
repo-root env file, or the container environment).
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

_API_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_API_ROOT.parents[1] / ".env")

from app.service.retention import run  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply retention by session class.")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None)
    parser.add_argument(
        "--apply", action="store_true", help="Actually delete; the default is a dry run."
    )
    args = parser.parse_args(argv)
    report = run(as_of=args.as_of, dry_run=not args.apply)
    sys.stdout.write(json.dumps(report.model_dump(mode="json"), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
