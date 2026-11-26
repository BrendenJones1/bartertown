"""Command-line entry point. Subcommands are filled in by the CLI issue."""

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paperclip")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a tournament from a config file")
    run.add_argument("--config", required=True)
    run.add_argument("--out", default="results")

    sub.add_parser("smoke", help="Run one short game with mock agents (no network)")

    args = parser.parse_args(argv)
    print(f"`paperclip {args.command}` is not implemented yet.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
