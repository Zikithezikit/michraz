# Changelog

All notable changes are listed here. Format based on [Keep a Changelog](https://keepachangelog.com/).

## Unreleased

### Added
- `GovSource` (`gov`): central-government tenders from mr.gov.il, read from the portal's HTML search. It is part of
  the default sources.
- Tests use a fixed clock, so open/closed results no longer depend on the date the suite runs.
- `HttpClient.get_text` for sources that serve HTML.

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
