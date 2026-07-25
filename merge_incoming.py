#!/usr/bin/env python3
"""
RegRisk Radar — incoming drop-file merger (v2, hardened 2026-07-25).

The nightly run publishes by writing a SMALL drop file to incoming/
(e.g. incoming/2026-07-25.json) instead of editing items.json directly
(items.json outgrew the connector's read/write limits). The merge Action
(.github/workflows/merge.yml) runs this script on every push to incoming/.

v2 changes (2026-07-25, after a 4-day stall caused by one malformed drop
file damming the whole queue, and by merge commits not triggering render.yml
because GITHUB_TOKEN pushes never trigger workflows):

  1. PER-FILE QUARANTINE instead of fail-everything. A drop file that is
     invalid (bad JSON, wrong shape, missing required fields, gated-layer or
     unknown fields) is QUARANTINED — renamed to
     incoming/rejected-<name>.txt with a rejected-<name>.reason.txt note —
     and every other valid drop file still merges. The compliance line is
     unchanged: an entry carrying a gated or unknown field is NEVER merged;
     it is quarantined for human review instead of silently dropped.
  2. TOLERANT NORMALIZATION of known-benign variants: a top-level "items"
     key is accepted as an alias for "entries"; source_type/
     primary_source_status synonyms are mapped to schema enums (e.g.
     "primary" -> "primary_source", "confirmed" -> "retrieved"); values that
     still do not match a schema enum are DROPPED so the renderer's
     conservative default applies (never claims primary unless .gov);
     date-only "published" gets T00:00:00Z; relevant_to lists join to a
     string. Facts/titles/URLs are never altered.
  3. SELF RENDER + COMMIT when running inside GitHub Actions. Because
     commits made with GITHUB_TOKEN do not trigger other workflows, the
     merge job now runs render.py itself and commits items.json + all
     rendered outputs + incoming/ changes in one commit. render.yml still
     exists for direct edits to items.json/render.py and for manual
     workflow_dispatch runs.
  4. TIME-BASED CLEANUP so the pipeline can never silt up:
       - quarantined rejected-*.txt files older than QUARANTINE_MAX_DAYS
         are deleted automatically;
       - live items older than RETENTION_DAYS (by published date) rotate
         out of items.json into items-archive.json (nothing is lost; the
         archive is never read by the connector or the renderer, so
         items.json and every rendered surface stay bounded). NOTE: an
         archived item's #permalink anchor leaves the page; social permalinks
         older than RETENTION_DAYS will land on the page top.

Guarantees kept from v1:
  - Idempotent on id: an entry whose id already exists in items.json is
    skipped.
  - Gated layer (severity, operator_exposure, why_it_matters,
    deadline_or_next_date, watchlist_implication, non_obvious_signal) NEVER
    reaches items.json.
  - items.json stays sorted by published (desc).

Usage: python3 merge_incoming.py   (stdlib only — no install, no network)
"""
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
ITEMS = os.path.join(ROOT, "items.json")
ARCHIVE = os.path.join(ROOT, "items-archive.json")
INCOMING_DIR = os.path.join(ROOT, "incoming")

RETENTION_DAYS = 180        # live window for items.json / rendered surfaces
QUARANTINE_MAX_DAYS = 30    # auto-delete quarantined drop files after this

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
# Known-benign synonyms -> schema enums. Anything else is dropped (renderer
# default is conservative: primary only for .gov hosts).
SOURCE_TYPE_MAP = {
    "primary": "primary_source",
    "primary-source": "primary_source",
    "official": "primary_source",
    "coverage": "media_coverage",
    "media": "media_coverage",
    "secondary": "media_coverage",
}
PRIMARY_STATUS_MAP = {
    "confirmed": "retrieved",
    "verified": "retrieved",
    "fetched": "retrieved",
    "not_retrieved": "cited_by_coverage_not_retrieved",
    "not_available": "unavailable",
}


class DropFileError(Exception):
    pass


def entries_of(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise DropFileError("invalid JSON: %s" % e)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("entries", "items"):  # "items" accepted as benign alias
            if isinstance(data.get(key), list):
                return data[key]
    raise DropFileError(
        "expected a JSON array or an object with an 'entries' (or 'items') array")


def normalize(entry):
    """Benign normalization only. Never touches facts/title/URLs."""
    st = entry.get("source_type")
    if st is not None and st not in SOURCE_TYPES:
        mapped = SOURCE_TYPE_MAP.get(str(st).strip().lower())
        if mapped:
            entry["source_type"] = mapped
        else:
            entry.pop("source_type", None)  # renderer default takes over
    ps = entry.get("primary_source_status")
    if ps is not None and ps not in PRIMARY_STATUSES:
        mapped = PRIMARY_STATUS_MAP.get(str(ps).strip().lower())
        if mapped:
            entry["primary_source_status"] = mapped
        else:
            entry.pop("primary_source_status", None)
    pub = entry.get("published")
    if isinstance(pub, str) and len(pub) == 10 and pub.count("-") == 2:
        entry["published"] = pub + "T00:00:00Z"
    relto = entry.get("relevant_to")
    if isinstance(relto, list):
        entry["relevant_to"] = ", ".join(
            str(x).replace("_", " ") for x in relto)


def validate(entry):
    """Raises DropFileError on anything not mergeable. Gated/unknown fields
    are a hard stop for the WHOLE file (quarantine), by design."""
    if not isinstance(entry, dict):
        raise DropFileError("entry is not an object")
    eid = entry.get("id", "<missing id>")
    for key in entry:
        if key in GATED:
            raise DropFileError(
                "entry %s carries gated-layer field '%s' — the gated layer "
                "must NEVER be pushed to this public repo" % (eid, key))
        if key not in ALLOWED:
            raise DropFileError(
                "entry %s has unknown field '%s' (public-safe schema only)"
                % (eid, key))
    for key in REQUIRED:
        if not entry.get(key):
            raise DropFileError("entry %s missing required field '%s'"
                                % (eid, key))


def quarantine(path, reason):
    name = os.path.basename(path)
    dest = os.path.join(INCOMING_DIR, "rejected-%s.txt" % name)
    reason_file = os.path.join(INCOMING_DIR, "rejected-%s.reason.txt" % name)
    os.replace(path, dest)
    with open(reason_file, "w", encoding="utf-8") as f:
        f.write("Quarantined %s\nFile: %s\nReason: %s\n"
                "Fix the file content and re-push it as a fresh "
                "incoming/<date>.json drop (idempotent on id).\n"
                % (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   name, reason))
    print("QUARANTINED %s: %s" % (name, reason))


def clean_quarantine():
    """Delete quarantined files older than QUARANTINE_MAX_DAYS (date parsed
    from the original file name)."""
    removed = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=QUARANTINE_MAX_DAYS)
    for path in glob.glob(os.path.join(INCOMING_DIR, "rejected-*.txt")):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path))
        if not m:
            continue
        try:
            fdate = datetime.strptime(m.group(1), "%Y-%m-%d").replace(
                tzinfo=timezone.utc)
        except ValueError:
            continue
        if fdate < cutoff:
            os.remove(path)
            removed.append(os.path.basename(path))
    if removed:
        print("quarantine cleanup: deleted %d file(s) older than %d days: %s"
              % (len(removed), QUARANTINE_MAX_DAYS, ", ".join(removed)))


def sort_key(item):
    return item.get("published") or (item.get("date", "") + "T00:00:00Z")


def rotate_archive(data):
    """Move items older than RETENTION_DAYS (by published) from items.json
    to items-archive.json. Returns number archived."""
    cutoff = (datetime.now(timezone.utc)
              - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    live, old = [], []
    for it in data["items"]:
        (live if sort_key(it) >= cutoff else old).append(it)
    if not old:
        return 0
    if os.path.exists(ARCHIVE):
        with open(ARCHIVE, encoding="utf-8") as f:
            archive = json.load(f)
    else:
        archive = {"_note": ("Rotated RegRisk Radar entries older than the "
                             "%d-day live window. Full history; never read "
                             "by the renderer or the connector."
                             % RETENTION_DAYS),
                   "items": []}
    known = {i.get("id") for i in archive["items"]}
    archive["items"].extend(i for i in old if i.get("id") not in known)
    archive["items"].sort(key=sort_key, reverse=True)
    with open(ARCHIVE, "w", encoding="utf-8") as f:
        json.dump(archive, f, indent=2, ensure_ascii=False)
        f.write("\n")
    data["items"] = live
    print("retention: archived %d item(s) older than %d days to %s"
          % (len(old), RETENTION_DAYS, os.path.basename(ARCHIVE)))
    return len(old)


def render_and_commit(changed):
    """Inside GitHub Actions only: render the site and commit + push
    everything in one commit (GITHUB_TOKEN pushes don't trigger render.yml,
    so the merge job must render itself)."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        print("not in GitHub Actions: skipping render/commit (local test mode)")
        return
    if not changed:
        print("nothing changed; skipping render/commit")
        return
    subprocess.run([sys.executable, os.path.join(ROOT, "render.py")],
                   check=True, cwd=ROOT)
    run = lambda *a: subprocess.run(list(a), check=True, cwd=ROOT)
    run("git", "config", "user.name", "regrisk-merge-bot")
    run("git", "config", "user.email",
        "github-actions[bot]@users.noreply.github.com")
    paths = ["items.json", "incoming", "index.html", "feed.xml", "atom.xml",
             "feed.json", "latest.json", "sitemap.xml", "robots.txt"]
    if os.path.exists(ARCHIVE):
        paths.append("items-archive.json")
    run("git", "add", "-A", "--", *paths)
    status = subprocess.run(["git", "status", "--porcelain"],
                            check=True, cwd=ROOT, capture_output=True,
                            text=True).stdout.strip()
    if not status:
        print("git: nothing staged; skipping commit")
        return
    run("git", "commit", "-m", "radar: merge incoming drops + render [auto]")
    run("git", "push")
    print("committed and pushed merged data + rendered outputs")


def main():
    drops = sorted(p for p in glob.glob(os.path.join(INCOMING_DIR, "*.json")))
    clean_quarantine()

    with open(ITEMS, encoding="utf-8") as f:
        data = json.load(f)
    if "site" not in data or not isinstance(data.get("items"), list):
        print("MERGE FAILED: items.json does not have the expected "
              "{site, items} shape")
        sys.exit(1)

    items = data["items"]
    ids = {i.get("id") for i in items}
    added, skipped, bad_files, merged_files = [], [], [], []

    for path in drops:
        rel = os.path.relpath(path, ROOT)
        try:
            entries = entries_of(path)
            staged = []
            for entry in entries:
                normalize(entry)
                validate(entry)
                staged.append(entry)
        except DropFileError as e:
            quarantine(path, str(e))
            bad_files.append(rel)
            continue
        for entry in staged:
            if entry["id"] in ids:
                skipped.append(entry["id"])
                continue
            items.append(entry)
            ids.add(entry["id"])
            added.append(entry["id"])
        merged_files.append(path)

    items.sort(key=sort_key, reverse=True)
    data["items"] = items
    archived = rotate_archive(data)

    if added or archived:
        with open(ITEMS, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    # Delete only the drop files that fully merged (or were fully duplicate).
    for path in merged_files:
        os.remove(path)

    print("processed %d drop file(s); merged+removed %d; quarantined %d"
          % (len(drops), len(merged_files), len(bad_files)))
    print("added %d entr%s%s" % (len(added), "y" if len(added) == 1 else "ies",
          (": " + ", ".join(added)) if added else ""))
    if skipped:
        print("skipped %d already-present id(s): %s"
              % (len(skipped), ", ".join(skipped)))
    if bad_files:
        print("QUARANTINED file(s) need review: %s" % ", ".join(bad_files))
    print("items.json now holds %d live item(s)" % len(items))

    render_and_commit(changed=bool(added or archived or bad_files
                                   or merged_files))


if __name__ == "__main__":
    main()
