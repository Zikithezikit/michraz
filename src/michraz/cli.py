"""Command-line interface: ``michraz search`` and ``michraz sources``."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Sequence
from datetime import datetime

from michraz import _dates
from michraz._http import DEFAULT_CACHE_DIR
from michraz._version import __version__
from michraz.client import Michraz
from michraz.errors import MichrazError
from michraz.export import to_csv, to_dicts
from michraz.models import Tender
from michraz.sources import BaseSource, BeerShevaSource, RmiSource

SOURCE_NAMES = (RmiSource.name, BeerShevaSource.name)
DATE_FORMAT = "%Y-%m-%d %H:%M"
NO_DATE = "-"
MIN_TITLE_WIDTH = 20
COLUMN_GAP = 2
NUMBER_WIDTH = 14
ELLIPSIS = "\u2026"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="michraz", description="Search Israeli public tenders.")
    parser.add_argument("--version", action="version", version=f"michraz {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--no-cache", action="store_true", help="do not read or write the on-disk cache")
    commands = parser.add_subparsers(dest="command", required=True)

    search = commands.add_parser("search", parents=[common], help="search tenders")
    search.add_argument("--keyword", "-k", help="text to look for in the title or number")
    search.add_argument("--open", action="store_true", help="only tenders that can still receive submissions")
    search.add_argument("--source", choices=SOURCE_NAMES, help="search a single source")
    search.add_argument("--csv", metavar="FILE", help="also write the results to a CSV file (UTF-8 with BOM)")
    search.add_argument("--json", action="store_true", help="print JSON instead of a table")

    commands.add_parser(
        "sources", parents=[common], help="list sources, their attribution and when each was last fetched"
    )
    return parser


def _when(value: datetime | None) -> str:
    return value.astimezone(_dates.JERUSALEM).strftime(DATE_FORMAT) if value else NO_DATE


def _clip(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + ELLIPSIS


def _print_table(tenders: Sequence[Tender]) -> None:
    # Hebrew is printed in logical order and the terminal lays it out. The title goes last so the
    # fixed-width columns stay aligned whatever the text direction.
    header = ("SOURCE", "NUMBER", "DEADLINE", "STATE")
    rows = [
        (t.source, _clip(t.number or NO_DATE, NUMBER_WIDTH), _when(t.deadline), "open" if t.is_open() else "closed")
        for t in tenders
    ]
    widths = [max(len(cells[i]) for cells in [header, *rows]) for i in range(len(header))]
    title_width = max(shutil.get_terminal_size().columns - sum(widths) - COLUMN_GAP * len(widths), MIN_TITLE_WIDTH)

    def line(cells: Sequence[str], title: str) -> str:
        fixed = (COLUMN_GAP * " ").join(cell.ljust(width) for cell, width in zip(cells, widths, strict=True))
        return f"{fixed}{COLUMN_GAP * ' '}{title}"

    print(line(header, "TITLE"))
    for cells, tender in zip(rows, tenders, strict=True):
        print(line(cells, _clip(tender.title, title_width)))
    print(f"\n{len(rows)} tender{'' if len(rows) == 1 else 's'}")
    for credit in sorted({t.attribution for t in tenders}):
        print(f"Data: {credit}")


def _search(args: argparse.Namespace, m: Michraz) -> int:
    tenders = m.search(keyword=args.keyword, open_only=args.open, source=args.source)
    if args.csv:
        count = to_csv(tenders, args.csv)
        print(f"wrote {count} tenders to {args.csv}", file=sys.stderr)
    if args.json:
        print(json.dumps(to_dicts(tenders), ensure_ascii=False, indent=2))
    else:
        _print_table(tenders)
    for message in m.last_errors:
        print(f"warning: {message}", file=sys.stderr)
    return 0


def _sources(m: Michraz) -> int:
    for source in m.sources:
        fetched = source.last_fetched() if isinstance(source, BaseSource) else None
        print(f"{source.name}\n  {source.description}\n  data: {source.attribution}\n  last fetch: {_when(fetched)}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Runs the command-line interface.

    Args:
        argv: Arguments without the program name. Defaults to ``sys.argv[1:]``.

    Returns:
        The process exit code: 0 on success, 1 if a source failed.
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # a console that cannot show Hebrew must not crash the run
    args = _build_parser().parse_args(argv)
    try:
        with Michraz(cache_dir=None if args.no_cache else DEFAULT_CACHE_DIR) as m:
            return _search(args, m) if args.command == "search" else _sources(m)
    except MichrazError as exc:
        print(f"michraz: error: {exc}", file=sys.stderr)
        return 1
