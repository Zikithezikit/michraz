# Changelog

All notable changes are listed here. Format based on [Keep a Changelog](https://keepachangelog.com/).

## 0.2.0 (2026-11-05)

### Added
- `BidsSource` and one small class per city for 12 municipalities that share the `/bids/` page layout (Akko, Arad,
  Beit Shemesh, Dimona, Kfar Saba, Kiryat Motzkin, Nesher, Netivot, Nof HaGalil, Savyon, Tamra, Yavne). They are
  part of the default sources.
- `michraz.sources.BUILT_IN` and `default_sources()`: one registry of every built-in source. `SourceName` lists all
  of them, and the CLI `--source` choices and the default search both follow the registry.
- `GovSource` (`gov`): central-government tenders from mr.gov.il, read from the portal's HTML search. It is part of
  the default sources.
- Tests use a fixed clock, so open/closed results no longer depend on the date the suite runs.
- `HttpClient.get_text` for sources that serve HTML.

### Changed
- `BaseSource` is now a template. A source implements `records()` and `parse(record)`, and the shared `fetch()`
  skips and reports bad records and drops repeated tenders. `RmiSource.fetch()` is now lazy like the others.
- `Tender.kind` (`TenderKind.TENDER` or `VACANCY`) and a `kind` filter on `Michraz.search` and the CLI
  (`--kind`). Staff vacancies that some municipal sites list beside their tenders are hidden by default. Pass
  `kind=None` for everything. The CSV has a new `kind` column.
- `Michraz.search` no longer fails when only some sources are down. Their errors go to `last_errors`, and it raises
  only if every searched source failed.

### Fixed
- Kiryat Motzkin: rows about the tender committee (`ועדת מכרזים`, meetings and protocols) are no longer returned as
  tenders.

### Upgrading from 0.1.0
- A default `Michraz()` search now reads 15 sources instead of 2. The first search takes about 20 seconds, mostly
  because mr.gov.il is read page by page. Responses are cached for an hour, so later searches are fast. Use
  `source="rmi"` (or any other name) to search one source.
- Every `Tender` has a `kind`, and `to_dicts` and the CSV include it. `Michraz.search` hides staff vacancies by
  default. Pass `kind=None` to get everything.
- `RmiSource.fetch()` returns a lazy iterator like the other sources. Use `search()` for a list.

## 0.1.0 (2026-11-05)

### Added
- `TenderFilter`, a frozen value object holding the search conditions (`matches`, `apply`). `Michraz.search` uses it.
- Enums instead of loose strings: `SourceName`, `RmiExtra` and `BeerShevaExtra` (keys of `Tender.extra`). Members
  equal the plain strings, so existing code keeps working.
- `Michraz` facade: search every source with one call, filter by keyword, open status, source and closing date,
  sorted by deadline.
- `RmiSource` for Israel Land Authority tenders, with server-side settlement and neighborhood filters and local
  filters for number, region, type, purpose and status. Ships a verified settlement name table.
- `BeerShevaSource` for Beer Sheva municipal tenders from data.gov.il, with CKAN pagination.
- Normalized `Tender` and `Document` models. All datetimes are timezone-aware (Asia/Jerusalem).
- `to_csv` (UTF-8 with BOM, formula-safe), `to_dicts` and `to_dataframe`.
- `michraz search` and `michraz sources` commands, also available as `python -m michraz`.
- Polite HTTP client: honest User-Agent, per-host rate limit, on-disk cache, bounded retries, `Retry-After`.
- `SourceUnavailableError` and `SourceFormatError`. A record that fails to parse is skipped and reported in
  `last_errors`.
- Repository skeleton: packaging, CI, release and manual live-smoke workflows, contributor docs.
