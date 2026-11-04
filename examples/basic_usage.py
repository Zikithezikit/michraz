"""Search open tenders across every source and print those closing within a week.

Talks to the real services. Responses are cached for an hour in ~/.cache/michraz.
"""

from datetime import datetime, timedelta, timezone

from michraz import Michraz, MichrazError

with Michraz() as m:
    try:
        week = datetime.now(timezone.utc) + timedelta(days=7)
        tenders = m.search(open_only=True, closing_before=week)
    except MichrazError as exc:
        raise SystemExit(f"could not fetch tenders: {exc}") from exc

    for tender in tenders:
        print(f"{tender.deadline:%Y-%m-%d %H:%M}  {tender.source:<9}  {tender.title}")
        print(f"    {tender.url}")

    print(f"\n{len(tenders)} tenders closing within a week")
    if m.last_errors:
        print(f"{len(m.last_errors)} records could not be parsed")
