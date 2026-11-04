# Data model

Every source produces the same two types. Both are frozen dataclasses with slots, so they are cheap, hashable and
safe to share.

## `Tender`

| Field | Type | RMI | Beer Sheva |
|-------|------|-----|------------|
| `source` | `str` | `"rmi"` | `"beersheva"` |
| `source_id` | `str` | `MichrazID` | list-item `ID` from the tender page URL |
| `title` | `str` | settlement and neighborhood, for example `אלפי מנשה - גבעת טל`. The API has no title field. | `שם מכרז` |
| `number` | `str \| None` | `MichrazName`, for example `115/2017` | `מספר מכרז`, or None when the row has none |
| `publisher` | `str \| None` | `רשות מקרקעי ישראל` | `עיריית באר שבע` |
| `published_at` | `datetime \| None` | `PirsumDate` | not available |
| `opens_at` | `datetime \| None` | `PtichaDate` | not available |
| `deadline` | `datetime \| None` | `SgiraDate` | `תאריך אחרון להגשה` |
| `updated_at` | `datetime \| None` | not available | `תאריך עדכון` |
| `winner` | `str \| None` | always None | `זוכה במכרז`, None when blank |
| `url` | `str \| None` | `https://apps.land.gov.il/MichrazimSite/#/michraz/{id}` | `URL` |
| `documents` | `tuple[Document, ...]` | empty (details endpoint not used yet) | links parsed from `קבצים` |
| `attribution` | `str` | credit line, always present | credit line, always present |
| `extra` | `Mapping[str, Any]` | see below | `payment_url`, `raw` |

Rules that hold for every source:

- Every datetime is timezone-aware and expressed in `Asia/Jerusalem`. A naive datetime is never produced or accepted.
- Hebrew text is kept as published. Whitespace is trimmed and HTML entities are decoded; nothing is translated or
  normalized.
- `extra["raw"]` is the untouched source record.
- Equality and hashing ignore `extra`.

`Tender.key` is `(source, source_id)`. `Tender.is_open(now=None)` is true when there is no winner and the
deadline is strictly after `now`. A tender with no known deadline counts as closed.

### RMI `extra`

| Key | Meaning |
|-----|---------|
| `settlement_code`, `settlement` | `KodYeshuv` and its Hebrew name from the authority's settlement table |
| `neighborhood` | `Shchuna`, trimmed |
| `region_code`, `type_code`, `purpose_code`, `status_code` | the authority's numeric codes. No official label table could be verified, so none is shipped. |
| `housing_units` | `YechidotDiur` |
| `committee_at` | `VaadaDate` |
| `khal_yaad_rashi` | `KhalYaadRashi`, kept as is. Observed values are 1, 2 and null, so it is a code and not a bid amount. |
| `mekuvan` | `Mekuvan`, kept as is. Its meaning is unconfirmed. |

## `Document`

| Field | Type | Meaning |
|-------|------|---------|
| `title` | `str` | link text as published (the URL if the link has no text) |
| `url` | `str` | absolute URL of the file |
