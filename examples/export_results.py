"""Save search results as CSV (opens in Excel with Hebrew intact), as dictionaries, or as a DataFrame."""

import json

from michraz import Michraz, to_csv, to_dataframe, to_dicts

with Michraz() as m:
    tenders = m.search(keyword="גינון", open_only=True)

count = to_csv(tenders, "gardening_tenders.csv")
print(f"wrote {count} tenders to gardening_tenders.csv")

print(json.dumps(to_dicts(tenders)[:1], ensure_ascii=False, indent=2))

try:
    frame = to_dataframe(tenders)  # needs: pip install "michraz[pandas]"
except ImportError as exc:
    print(exc)
else:
    print(frame[["source", "number", "deadline", "title"]].head())
