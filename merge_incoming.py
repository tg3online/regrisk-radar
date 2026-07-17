#!/usr/bin/env python3
"""
RegRisk Radar — incoming drop-file merger.

The nightly run publishes by writing a SMALL drop file to incoming/
(e.g. incoming/2026-07-16.json) instead of editing items.json directly
(items.json outgrew the connector's read/write limits). The merge Action
(.github/workflows/merge.yml) runs this script on every push to incoming/,
then runs render.py and commits items.json + all rendered outputs, deleting
the processed drop files in the same commit.

Drop file format: either a JSON array of item objects, or an object with an
"entries" array (extra top-level keys such as "_note" are ignored).

Guarantees:
  - Idempotent on id: an entry whose id already exists in items.json is skipped.
  - PUBLIC-SAFE fields only: an entry carrying a gated-layer field (severity,
    operator_exposure, why_it_matters, deadline_or_next_date,
    watchlist_implication, non_obvious_signal) or any unknown field FAILS the
    whole merge — nothing is committed. The gated layer must never reach this
    public repo.
  - items.json stays sorted by published (desc).

Usage: python3 merge_incoming.py   (stdlib only — no install, no network)
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ITEMS = os.path.join(ROOT, "items.json")
INCOMING_DIR = os.path.join(ROOT, "incoming")

REQUIRED = ("id", "date", "published", "issuing_body", "title", "facts",
            "source_url", "source_label")
OPTIONAL = ("tags", "source_type", "primary_source_status", "relevant_to")
ALLOWED = set(REQUIRED) | set(OPTIONAL)
GATED = ("severity", "operator_exposure", "why_it_matters",
         "deadline_or_next_date", "watchlist_implication", "non_obvious_signal")
SOURCE_TYPES = ("primary_source", "coverage_reporting_filing",
                "media_coverage", "mixed")
PRIMARY_STATUSES = ("retrieved", "cited_by_coverage_not_retrieved",
                    "unavailable")


def fail(msg):
    print("MERGE FAILED: %s" % msg)
    sys.exit(1)


def entries_of(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data["entries"]
    fail("%s: expected a JSON array or an object with an 'entries' array" % path)


def validate(entry, path):
    if not isinstance(entry, dict):
        fail("%s: entry is not an object" % path)
    eid = entry.get("id", "<missing id>")
    for key in entry:
        if key in GATED:
            fail("%s: entry %s carries gated-layer field '%s' — the gated "
                 "layer must NEVER be pushed to this public repo" % (path, eid, key))
        if key not in ALLOWED:
            fail("%s: entry %s has unknown field '%s' (public-safe schema only)"
                 % (path, eid, key))
    for key in REQUIRED:
        if not entry.get(key):
            fail("%s: entry %s missing required field '%s'" % (path, eid, key))
    st = entry.get("source_type")
    if st is not None and st not in SOURCE_TYPES:
        fail("%s: entry %s has invalid source_type '%s'" % (path, eid, st))
    ps = entry.get("primary_source_status")
    if ps is not None and ps not in PRIMARY_STATUSES:
        fail("%s: entry %s has invalid primary_source_status '%s'" % (path, eid, ps))


def sort_key(item):
    return item.get("published") or (item.get("date", "") + "T00:00:00Z")


def main():
    drops = sorted(glob.glob(os.path.join(INCOMING_DIR, "*.json")))
    if not drops:
        print("no incoming drop files; nothing to merge")
        return

    with open(ITEMS, encoding="utf-8") as f:
        data = json.load(f)
    if "site" not in data or not isinstance(data.get("items"), list):
        fail("items.json does not have the expected {site, items} shape")

    items = data["items"]
    ids = {i.get("id") for i in items}
    added, skipped = [], []

    for path in drops:
        rel = os.path.relpath(path, ROOT)
        for entry in entries_of(path):
            validate(entry, rel)
            if entry["id"] in ids:
                skipped.append(entry["id"])
                continue
            items.append(entry)
            ids.add(entry["id"])
            added.append(entry["id"])

    items.sort(key=sort_key, reverse=True)
    data["items"] = items

    if added:
        with open(ITEMS, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    print("processed %d drop file(s): %s" % (len(drops),
          ", ".join(os.path.relpath(p, ROOT) for p in drops)))
    print("added %d entr%s%s" % (len(added), "y" if len(added) == 1 else "ies",
          (": " + ", ".join(added)) if added else ""))
    if skipped:
        print("skipped %d already-present id(s): %s" % (len(skipped), ", ".join(skipped)))
    print("items.json now holds %d items" % len(items))


if __name__ == "__main__":
    main()
