# Sources

What each source is, how it was checked, and what is still unknown. Everything marked *verified* was observed
against the live service on 2026-11-04 by running the code in this repository. Everything marked *not verified*
says so.

## Israel Land Authority (RMI), `rmi`

- Endpoint: `POST https://apps.land.gov.il/MichrazimSite/api/SearchApi/Search`, JSON body, no authentication.
- Attribution: `Israel Land Authority (רשות מקרקעי ישראל), apps.land.gov.il`.
- Refresh: live.
- Verified: `{"ActiveQuickSearch": false, "ActiveMichraz": true}` returned 441 open tenders and the field set in
  `tests/fixtures/rmi_search.json`. An honest `michraz/...` User-Agent is accepted. `ActiveMichraz: false` returned
  10 222 tenders, the whole archive.
- The server does not paginate. One call returns every match.

### Request filters

Each key from the upstream `barvhaim/remy-mcp` client was sent alone and the result compared with the same filter
applied locally to the unfiltered list.

| Key | Result | What michraz does |
|-----|--------|-------------------|
| `KodYeshuv` (int) | verified: server returned exactly the matching tenders | sent to the server |
| `Shchuna` (string) | verified: server returned exactly the matching tender | sent to the server |
| `MisMichraz`, `SugMichraz`, `YeudMichraz`, `Merchav`, `StatusMichraz` | ignored: all 441 came back | filtered locally on the returned codes |
| `CloseDate` as `{"from","to"}` in `dd/mm/yy` | ignored: all 441 came back | not exposed. Use `closing_before` and `closing_after` on `Michraz.search`. |
| `VaadaDate`, `PirsumDate`, `PriorityPopulations` | not tested | not exposed. `raw_filters` can send them, unsupported. |

The keys might work with a different value shape. The ones that were ignored are simply not relied on.

### Code tables

- **Settlements (`KodYeshuv`)**: verified and shipped. The table comes from the authority's own
  `GET /MichrazimSite/api/YeshuvimApi/Get`, fetched 2026-11-04, 1427 entries, stored in
  `src/michraz/sources/data/rmi_settlements.json`. Every one of the 441 tenders resolves to a name.
- **Region, type, purpose, status**: not shipped. The `remy-mcp` tables (MIT, commit `b2bf732`) do not match the
  live data. The live API uses 7 region codes where remy lists 6, tender types up to 11 where remy lists 9, and
  purposes up to 99 where remy lists 9. Cross-checking tenders against the region the authority assigns to their
  settlement shows that region 7 is Judea and Samaria, while remy labels region 1 that way. Without an official
  source the codes are exposed raw under `extra`.

### Tender page URL

`https://apps.land.gov.il/MichrazimSite/#/michraz/{MichrazID}`. The site's JavaScript bundle defines the route
`michraz/:michrazID` and enables hash routing. The URL was not opened in a browser, so the link is believed
correct and not confirmed.

### Fields with unknown meaning

- `KhalYaadRashi` is only ever 1, 2 or null across the 441 open tenders. It is not a bid amount.
- `Mekuvan` is true for 422 of 441 tenders. `remy-mcp` calls it "reserved"; that is not consistent with the data.
- `VaadaDate` was null for every open tender.

### Not used yet

`GET /MichrazDetailsApi/Get?michrazID=` (details, documents) and `GetMichrazMapaDetails`. Planned after 0.1.

## Beer Sheva municipality, `beersheva`

- Endpoint: CKAN datastore, `GET https://data.gov.il/api/3/action/datastore_search?resource_id=6a281768-6327-420b-a1c5-fb84af1fa8ae`.
  Dataset `tender-br7`.
- Attribution: `Beer Sheva Municipality (עיריית באר שבע), via data.gov.il, license: Other (Open)`.
- Refresh: weekly, as stated by the publisher.
- Verified: 837 rows. A single request with `limit=1000` returns all of them, so the default page size is 1000.
  Pagination follows `result.total` and `offset` and is covered by tests with a small page size.
- License: `package_show` reports `license_id: other-open`, "Other (Open)", organization עיריית באר שבע.

### Data quality observed (837 rows)

- `מספר מכרז` is empty in 41 rows and repeats in two cases, so it cannot be a key. michraz uses the list-item
  `ID` from the `URL` column (unique across all rows) as `source_id` and keeps the number as `number`.
- Numbers and names can contain HTML entities such as `&#39;`. They are decoded.
- 5 rows have an empty deadline and 3 an empty update date. They become None.
- 402 rows have a winner, 51 have no files. `קבצים` is HTML that is not always wrapped in `<p>`, and some links
  encode the URL as `http&#58;//...`. It is read with `html.parser`.

## Central government, `gov`

- Portal: the Government Procurement Administration's tender site, `https://mr.gov.il/ilgstorefront/he/search/`.
  It has no JSON API. The search page is server-rendered HTML, 20 results per page, `page` starts at 0.
- Attribution: `Government Procurement Administration (מינהל הרכש הממשלתי), mr.gov.il`. The license of the data was
  not checked.
- Query: `q=:updateDate:archive:false:status:<status>`, `s=TENDER`. The portal reports 8 835 tenders in total, 7 654
  of them with status `חלף מועד הגשה` (submission date passed). michraz reads only the statuses `פורסם`, `עודכן` and
  `חדש`.
- Verified on 2026-11-05: those three statuses returned 123, 256 and 40 tenders. Reading all of them gave 419
  tenders and 0 parse errors in about 21 seconds. 183 had a deadline still ahead and 14 had no deadline.
- Fields read: title, type (`מכרז פומבי`), publisher, publication number (used as `source_id`), procedure number
  (used as `number`), publication date, update date, deadline (`dd/mm/yyyy HH:MM`) and status.
- Not verified: statuses `בעדכון` (32) and `עתידי` (15) are not read, because it is unclear whether they accept
  offers. Detail pages and attached documents are not fetched, so `documents` is empty.
- `tests/fixtures/gov_search.html` is five real result blocks copied from a live page. The embedded images were
  removed and the count sentence was edited to say 5 so that it matches the excerpt.
- The site has no `robots.txt` (the request returns an empty body).

## Robots and terms

Checked 2026-11-04 from the development machine with the michraz User-Agent.

| Host | `robots.txt` |
|------|--------------|
| `apps.land.gov.il` | HTTP 404, no robots file |
| `data.gov.il` | `User-agent: *`, `Allow: /`, **`Disallow: /api/`** |

The `data.gov.il` file disallows `/api/` for all agents, and the Beer Sheva source calls
`/api/3/action/datastore_search`. That is the portal's documented open-data API, michraz makes one cached request per
search, and the maintainer reviewed this on 2026-11-04 and decided to keep the source enabled. Terms of use pages
were not reviewed.

## Known dead ends

- The national Procurement Administration datasets on data.gov.il (`tenders`, `exemptions`) stopped updating in
  2021 according to the maintainer. They are historical only and are not a source. This was not re-checked here.
- BudgetKey (`next.obudget.org`) has no tenders table according to the maintainer. Not a source.
