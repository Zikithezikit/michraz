# michraz

[![PyPI](https://img.shields.io/pypi/v/michraz)](https://pypi.org/project/michraz/)
[![Python](https://img.shields.io/pypi/pyversions/michraz)](https://pypi.org/project/michraz/)
[![CI](https://github.com/Zikithezikit/michraz/actions/workflows/ci.yml/badge.svg)](https://github.com/Zikithezikit/michraz/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/Zikithezikit/michraz/blob/main/LICENSE)

Israeli public tenders (מכרזים) in Python, from one place.

Each publisher has its own site and its own format. michraz reads the machine-readable feeds those sites already
offer and returns the same `Tender` object for all of them. You can search, filter, export to CSV, or use the
command line.

It reads Israel Land Authority land tenders and Beer Sheva municipal tenders. Another municipality is one small
class.

> michraz is an unofficial client. It can lag or miss tenders and parsing can break when a source changes. Always
> confirm deadlines and conditions on the publisher's official page before you act. Not affiliated with the Israel Land
> Authority or any municipality.

## Install

```bash
pip install michraz
```

Python 3.10 or newer. If you want DataFrames, install `michraz[pandas]`.

## Quick start

```python
from michraz import Michraz

with Michraz() as m:
    for tender in m.search(keyword="גינון", open_only=True):
        print(f"{tender.deadline:%Y-%m-%d}  {tender.title}")
        print(f"  {tender.url}")
```

Results are sorted by deadline; tenders without one come last. Every tender has an `attribution` string. Keep it
when you pass the data on.

![What michraz does](https://raw.githubusercontent.com/Zikithezikit/michraz/main/docs/images/overview.png)

## From the terminal

```bash
michraz search --open --source rmi
michraz search --keyword גינון --csv gardening.csv
michraz search --json | jq '.[0]'
michraz sources
```

```text
SOURCE  NUMBER    DEADLINE          STATE  TITLE
rmi     323/2021  2026-11-09 12:00  open   אשקלון - אגמים
rmi     389/2021  2026-11-09 12:00  open   רמלה - איצטדיון
rmi     15/2023   2026-11-09 12:00  open   כפר קרע - סטאלין

441 tenders
Data: Israel Land Authority (רשות מקרקעי ישראל), apps.land.gov.il
```

Hebrew is printed in logical order, so the terminal handles the right-to-left layout. The CSV has a byte order mark
so Excel shows the Hebrew correctly. Add `--no-cache` to skip the on-disk cache. The exit
code is 1 if a service could not be reached.

## Recipes

Ask a single source, with its own filters:

```python
from michraz import RmiExtra, RmiSource

with RmiSource() as rmi:
    for tender in rmi.search(settlement_code=3750):
        print(tender.number, tender.title, tender.extra[RmiExtra.HOUSING_UNITS])
```

Tenders closing in a window (plain dates mean midnight in Israel):

```python
from datetime import date

m.search(closing_after=date(2026, 12, 1), closing_before=date(2027, 1, 1))
```

Save the results:

```python
from michraz import to_csv, to_dicts, to_dataframe

to_csv(tenders, "tenders.csv")
to_dicts(tenders)  # plain dictionaries, ready for json.dumps
to_dataframe(tenders)  # needs michraz[pandas]
```

Source names and the keys of `tender.extra` are enums (`SourceName`, `RmiExtra`, `BeerShevaExtra`). They equal
the plain strings, so `source="rmi"` and `tender.extra["housing_units"]` also work.

A tender is open when it has no winner and its deadline is still ahead. A deadline equal to the current moment counts
as closed, and so does a tender with no deadline at all.

A record that cannot be parsed is skipped, logged, and listed in `m.last_errors`. An unreachable service raises
`SourceUnavailableError`, and an unexpected response shape raises `SourceFormatError`. Both inherit from
`MichrazError`.

The [examples](https://github.com/Zikithezikit/michraz/tree/main/examples) folder has runnable scripts. One of them,
`custom_source.py`, adds a made-up municipality and runs without a network connection.

## Adding a source

A source is any object with a `name`, a `description`, an `attribution`, an `errors` list and a `fetch()` method that
yields `Tender` objects. Pass it to `Michraz([MySource()])` and it takes part in searches like the built-in ones.

![Classes](https://raw.githubusercontent.com/Zikithezikit/michraz/main/docs/images/classes.png)

The fields of `Tender` and which source fills which are listed in
[docs/model.md](https://github.com/Zikithezikit/michraz/blob/main/docs/model.md).

## What happens during a search

Every request goes through one client that rate-limits, caches on disk and identifies itself.

![Request flow](https://raw.githubusercontent.com/Zikithezikit/michraz/main/docs/images/request_flow.png)

It sends `michraz/<version> (+https://github.com/Zikithezikit/michraz)` as its User-Agent, waits at least a second
between requests to the same host, caches responses for an hour in `~/.cache/michraz`, and retries at most twice on
429 and 5xx, honoring `Retry-After`. Tuning:

```python
from datetime import timedelta

Michraz(cache_dir=None)  # no cache
Michraz(cache_ttl=timedelta(minutes=10))  # shorter cache
Michraz(min_interval=3.0)  # slower; values below 0.5 are rejected
```

## Sources

| Source | What it covers | How fresh | Credit line |
|--------|----------------|-----------|-------------|
| `rmi` | Open land tenders of the Israel Land Authority | live | Israel Land Authority (רשות מקרקעי ישראל), apps.land.gov.il |
| `beersheva` | Beer Sheva municipal tenders, open and past, from data.gov.il | refreshed weekly | Beer Sheva Municipality (עיריית באר שבע), via data.gov.il, license: Other (Open) |

Keep the credit line when you republish the data. The CSV has a column for it and the CLI prints it under the table. How each source was checked, and what is still unknown, is written down in
[docs/sources.md](https://github.com/Zikithezikit/michraz/blob/main/docs/sources.md).

## Known limitations

The Israel Land Authority publishes region, tender type, purpose and status as numbers. The only public label table
I found did not match the live data, so `tender.extra` holds the raw codes (`RmiExtra.REGION_CODE` and friends). Settlement names come from the
authority's own list.

Of the filters the RMI search accepts, only settlement and neighborhood actually work on the server. michraz
downloads the list and applies the others (tender number, region, type, purpose, status) itself.

The link in `tender.url` for RMI tenders follows the site's own route definition, but I have not opened it in a
browser to confirm it lands on the right tender. RMI tender details and attached documents are not fetched yet, so
`documents` is empty for those. Two fields, `khal_yaad_rashi` and `mekuvan`, are passed through as the API sends them
because their meaning is not documented.

Beer Sheva tender numbers are sometimes blank or repeated, so those tenders are identified by the municipality's own
item id instead.

Keyword search is a plain substring match after Unicode normalization. It does not do stemming, so `גינון` will not
find `גינה`. The sources' terms of use have not been reviewed.

## Development

```bash
make venv
make check         # ruff, mypy --strict and pytest, the same as CI
make cov           # coverage report
pytest -m live     # calls each real service once; manual only
make diagrams      # redraw the pictures in this README (needs Graphviz)
```

The test suite never touches the network. It runs against recorded responses, and a guard fails any test that opens
a socket. See [CONTRIBUTING.md](https://github.com/Zikithezikit/michraz/blob/main/CONTRIBUTING.md) before opening a
pull request.

## License

MIT. The data belongs to the people who publish it and comes with their licenses.
