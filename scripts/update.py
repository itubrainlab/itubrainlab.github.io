#!/usr/bin/env python3
"""Refresh the brAIn lab site content from ITU's Pure research portal.

Reads the three Pure RSS feeds and writes plain Markdown into content/data/:

    content/data/publications.md   <- .../brain-lab/publications/?format=rss
    content/data/datasets.md       <- .../brain-lab/datasets/?format=rss
    content/data/people.md         <- .../brain-lab/persons/?format=rss

Standard library only -- no pip install, no build step.

Usage:
    python3 scripts/update.py                 # all three feeds, English portal
    python3 scripts/update.py --lang da       # use the Danish Pure portal
    python3 scripts/update.py publications    # refresh one feed only
    python3 scripts/update.py --dry-run

Note on datasets: the human-readable page at
https://pure.itu.dk/en/organisations/brain-lab/datasets/ sits behind a
Cloudflare browser challenge and cannot be scraped from a script. The
?format=rss view of that same listing is not challenged and carries the same
records, so that is what this script reads.
"""

import argparse
import base64
import html
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

BASE = "https://pure.itu.dk/{lang}/organisations/brain-lab/{section}/?format=rss"

FEEDS = {
    "publications": {"section": "publications", "out": "publications.md"},
    "datasets":     {"section": "datasets",     "out": "datasets.md"},
    "people":       {"section": "persons",      "out": "people.md"},
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "content", "data")

# Portraits. Pure's person feed carries no images, so each person's Pure page is
# fetched and the portrait pulled out of it, then saved locally — the site stays
# self-contained rather than hotlinking pure.itu.dk on every page view.
# Most people have no portrait uploaded; those get a generated initials
# monogram so the contacts list stays visually even.
PHOTO_DIR = os.path.join(ROOT, "assets", "img", "people")
PHOTO_REL = "assets/img/people"
PHOTO_WIDTH = 320        # 2x the 76px the page renders them at, for retina

# Muted tints for the monograms, picked deterministically from the name.
MONOGRAM_TINTS = ["#f3e6e9", "#eceaf0", "#e9eef0", "#f1ece5", "#eaeeea"]

# The people list is split into "Lab Coordinators" and "Lab Members". Anyone
# matched here lands in the first group, in the order given; everyone else keeps
# the order Pure returned. Each entry is matched on the Pure person-page slug
# first, falling back to the display name, so a renamed slug does not silently
# demote someone to Lab Members. A coordinator missing from the feed is simply
# skipped -- the group only appears if at least one of them is present.
COORDINATORS = [
    {"slug": "stefan-heinrich", "name": "Stefan Heinrich"},
    {"slug": "paolo-burelli",   "name": "Paolo Burelli"},
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
TIMEOUT = 30


# --------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------

def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9,da;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return res.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise SystemExit(
                "error: Pure returned 403 for %s\n"
                "       This usually means a Cloudflare challenge. Check that the URL\n"
                "       still ends in '?format=rss' -- the plain HTML views are blocked." % url
            )
        raise SystemExit("error: HTTP %s fetching %s" % (e.code, url))
    except urllib.error.URLError as e:
        raise SystemExit("error: could not reach %s (%s)" % (url, e.reason))


# --------------------------------------------------------------------------
# small HTML helpers (Pure's RSS packs rendered HTML inside <description>)
# --------------------------------------------------------------------------

def strip_tags(fragment):
    """Reduce an HTML fragment to a single clean line of text."""
    text = re.sub(r"<[^>]+>", "", fragment or "")
    text = html.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def md_escape(text):
    """Escape the characters that would otherwise start Markdown markup."""
    return re.sub(r"([*_`\[\]])", r"\\\1", text)


def first_group(pattern, text, default=""):
    m = re.search(pattern, text, re.S)
    return m.group(1) if m else default


def parse_title(desc):
    """Return (title, url) from the <h3 class="title"> block."""
    block = first_group(r'<h3 class="title">(.*?)</h3>', desc)
    url = first_group(r'href="([^"]+)"', block)
    return strip_tags(block), html.unescape(url)


def parse_type(desc):
    return strip_tags(first_group(r'<p class="type">(.*?)</p>', desc))


def collect_dois(desc):
    """Return DOI links as (label, url) pairs, de-duplicated, order preserved."""
    block = first_group(r'<p class="links-doi">(.*?)</p>', desc)
    out, seen = [], set()
    for url in re.findall(r'href="(https?://[^"]+)"', block):
        url = html.unescape(url)
        if url in seen:
            continue
        seen.add(url)
        label = url.split("doi.org/", 1)[1] if "doi.org/" in url else url
        out.append((label, url))
    return out


def decode_pure_email(desc):
    """Pure obfuscates addresses as base64 'mailto:...' in a data-md5 attribute."""
    for token in re.findall(r'data-md5="([^"]+)"', desc):
        try:
            decoded = base64.b64decode(token + "===").decode("utf-8", "replace")
        except Exception:
            continue
        m = re.search(r"mailto:([^\s\"'<>]+@[^\s\"'<>]+)", decoded)
        if m:
            return m.group(1)
    return ""


def slugish(text):
    """Fallback slug for a person with no Pure URL, so the file still gets a name."""
    return ascii_slug(text) or "person"


def ascii_slug(text):
    """Fold to plain ASCII for use as a filename.

    Pure slugs can contain non-ASCII ('morten-ib-kjaergaard-munk' arrives as
    ...kj%C3%A6rgaard...). Keeping that in a filename invites trouble: URLs need
    escaping, and macOS stores decomposed forms while Linux servers do not, so
    the same name can round-trip differently on each. Fold it once here instead.
    """
    folded = unicodedata.normalize("NFKD", text or "")
    folded = folded.replace("ø", "o").replace("Ø", "O") \
                   .replace("æ", "ae").replace("Æ", "AE") \
                   .replace("å", "aa").replace("Å", "AA") \
                   .replace("ß", "ss").replace("đ", "d").replace("ł", "l")
    folded = folded.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")


def try_fetch(url, binary=False):
    """Best-effort fetch. Portraits are a nice-to-have, so failures are not fatal."""
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9,da;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            raw = res.read()
        return raw if binary else raw.decode("utf-8", "replace")
    except Exception:
        return None


def portrait_url(page_html):
    """Pull the portrait out of a Pure person page, at the size we want.

    Pure marks it up as <img src="/files-asset/..." class="image">. People
    without an uploaded portrait have no such tag at all — the page falls back
    to a generic placeholder — so returning None here is the normal case.
    """
    m = re.search(r'<img[^>]*src="(/files-asset/[^"]+)"[^>]*class="image"', page_html)
    if not m:
        return None
    src = html.unescape(m.group(1)).split("?")[0]
    return "https://pure.itu.dk%s?w=%d&f=jpg" % (src, PHOTO_WIDTH)


def monogram(name, slug):
    """An initials avatar for people with no portrait in Pure."""
    words = [w for w in re.split(r"[\s-]+", name) if w]
    initials = (words[0][0] + words[-1][0]).upper() if len(words) > 1 else \
               (words[0][:2].upper() if words else "?")
    tint = MONOGRAM_TINTS[sum(map(ord, slug)) % len(MONOGRAM_TINTS)]
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" '
        'width="160" height="160">\n'
        '  <rect width="160" height="160" fill="%s"/>\n'
        '  <text x="80" y="80" text-anchor="middle" dominant-baseline="central" '
        'font-family="Helvetica Neue, Helvetica, Arial, sans-serif" font-size="58" '
        'font-weight="600" fill="#bc0020" fill-opacity="0.72">%s</text>\n'
        '</svg>\n' % (tint, html.escape(initials))
    )


def save_portrait(name, url, slug, want_photos, write=True):
    """Return a site-relative image path for this person, or '' if we have none."""
    if not write:
        # --dry-run: report the monogram path without touching the filesystem
        return "%s/%s.svg" % (PHOTO_REL, slug)

    os.makedirs(PHOTO_DIR, exist_ok=True)

    if want_photos and url:
        page = try_fetch(url)
        if page:
            src = portrait_url(page)
            if src:
                blob = try_fetch(src, binary=True)
                # guard against an error page being saved as a .jpg
                if blob and len(blob) > 1024 and blob[:2] == b"\xff\xd8":
                    dest = os.path.join(PHOTO_DIR, slug + ".jpg")
                    with open(dest, "wb") as fh:
                        fh.write(blob)
                    return "%s/%s.jpg" % (PHOTO_REL, slug)

    dest = os.path.join(PHOTO_DIR, slug + ".svg")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(monogram(name, slug))
    return "%s/%s.svg" % (PHOTO_REL, slug)


def person_slug(url):
    """'https://pure.itu.dk/en/persons/paolo-burelli/' -> 'paolo-burelli'.

    Pure appends a numeric suffix when two people share a slug
    ('...-hristova-3'), so that is trimmed before comparing.
    """
    slug = urllib.parse.unquote(url or "").rstrip("/").rsplit("/", 1)[-1].lower()
    return re.sub(r"-\d+$", "", slug)


def coordinator_rank(name, url):
    """Index into COORDINATORS, or len(COORDINATORS) for everyone else."""
    slug = person_slug(url)
    clean = re.sub(r"\s+", " ", (name or "")).strip().lower()
    for i, coord in enumerate(COORDINATORS):
        if (slug and slug == coord["slug"]) or (clean and clean == coord["name"].lower()):
            return i
    return len(COORDINATORS)


def is_coordinator(name, url):
    return coordinator_rank(name, url) < len(COORDINATORS)


def item_year(item):
    """Best-effort publication year, for grouping."""
    for tag in ("{http://purl.org/dc/elements/1.1/}date", "pubDate"):
        raw = item.findtext(tag)
        if not raw:
            continue
        m = re.search(r"(19|20)\d{2}", raw)
        if m:
            return m.group(0)
    return "Undated"


def parse_items(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise SystemExit("error: feed was not valid XML (%s). Pure may have "
                         "returned an error page instead." % e)
    return root.findall("./channel/item")


# --------------------------------------------------------------------------
# renderers -- one per feed, each returning a Markdown string
# --------------------------------------------------------------------------

def render_publications(items, source_url):
    groups = {}
    for item in items:
        desc = item.findtext("description") or ""
        title, url = parse_title(desc)
        title = title or (item.findtext("title") or "").strip()
        url = url or (item.findtext("link") or "").strip()

        # everything between the title and the type line is the citation
        rest = desc.split("</h3>", 1)[1] if "</h3>" in desc else desc
        rest = re.sub(r'<p class="type">.*?</p>', "", rest, flags=re.S)
        rest = re.sub(r'<p class="links-doi">.*?</p>', "", rest, flags=re.S)
        citation = strip_tags(rest).strip().strip(",;").strip()

        groups.setdefault(item_year(item), []).append({
            "title": title, "url": url, "citation": citation,
            "type": parse_type(desc), "dois": collect_dois(desc),
        })

    lines = []
    for year in sorted(groups, key=lambda y: (y != "Undated", y), reverse=True):
        lines.append("## %s\n" % year)
        for rec in groups[year]:
            lines.extend(record_block(rec))
    return finish(lines, source_url, sum(len(v) for v in groups.values()), "publication")


def render_datasets(items, source_url):
    lines = []
    for item in items:
        desc = item.findtext("description") or ""
        title, url = parse_title(desc)
        title = title or (item.findtext("title") or "").strip()
        url = url or (item.findtext("link") or "").strip()

        rest = desc.split("</h3>", 1)[1] if "</h3>" in desc else desc
        rest = re.sub(r'<p class="type">.*?</p>', "", rest, flags=re.S)
        rest = re.sub(r'<p class="links-doi">.*?</p>', "", rest, flags=re.S)

        lines.extend(record_block({
            "title": title, "url": url,
            "citation": strip_tags(rest).strip().strip(",;").strip(),
            "type": parse_type(desc), "dois": collect_dois(desc),
        }))
    return finish(lines, source_url, len(items), "dataset")


def render_people(items, source_url, want_photos=True, write=True):
    lines = []
    coordinators, members = [], []

    for item in items:
        desc = item.findtext("description") or ""
        name, url = parse_title(desc)
        name = name or (item.findtext("title") or "").strip()
        url = url or (item.findtext("link") or "").strip()

        email = decode_pure_email(desc)
        orgs = [strip_tags(li) for li in
                re.findall(r"<li>(.*?)</li>",
                           first_group(r'<ul class="relations organisations">(.*?)</ul>', desc),
                           re.S)]
        # Pure's <p class="type"> for a person is just "Person: VIP" / "Person:
        # Guest" -- an internal staff category, not useful on a contacts page.
        person = {"name": name, "url": url, "email": email,
                  "orgs": [o for o in orgs if o],
                  "photo": save_portrait(name, url, ascii_slug(person_slug(url)) or slugish(name),
                                         want_photos, write)}

        (coordinators if is_coordinator(name, url) else members).append(person)

    # Coordinators keep the order of COORDINATORS; everyone else keeps feed order.
    coordinators.sort(key=lambda p: coordinator_rank(p["name"], p["url"]))

    for heading, group in (("Lab Coordinators", coordinators), ("Lab Members", members)):
        if not group:                      # skip a group the feed had nobody for
            continue
        lines.append("## %s\n" % heading)
        for person in group:
            lines.extend(person_block(person))

    return finish(lines, source_url, len(items), "person")


def person_block(person):
    out = []
    # Photo first so CSS can float it beside the name and details that follow.
    # Alt is empty on purpose: the name is the very next line, so announcing it
    # twice would only add noise for screen readers.
    if person.get("photo"):
        out.append("![](%s)\n" % person["photo"])
    out.append("### [%s](%s)\n" % (md_escape(person["name"]), person["url"]) if person["url"]
               else "### %s\n" % md_escape(person["name"]))
    if person["email"]:
        out.append("[%s](mailto:%s)\n" % (person["email"], person["email"]))
    if person["orgs"]:
        out.append("%s\n" % md_escape(" · ".join(person["orgs"])))
    return out


def record_block(rec):
    """Shared Markdown shape for a publication or dataset."""
    out = []
    out.append("### [%s](%s)\n" % (md_escape(rec["title"]), rec["url"]) if rec["url"]
               else "### %s\n" % md_escape(rec["title"]))
    if rec["citation"]:
        out.append("%s\n" % md_escape(rec["citation"]))
    if rec["dois"]:
        out.append("DOI: %s\n" % ", ".join("[%s](%s)" % (md_escape(l), u) for l, u in rec["dois"]))
    if rec["type"]:
        out.append("*%s*\n" % md_escape(rec["type"]))
    return out


def finish(lines, source_url, count, noun):
    if not lines:
        lines = ["_No %ss found in the feed._\n" % noun]
    header = (
        "<!-- GENERATED FILE - do not edit by hand.\n"
        "     Source: %s\n"
        "     Written by scripts/update.py on %s\n"
        "     %d %s%s -->\n"
    ) % (source_url,
         datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
         count, noun, "" if count == 1 else "s")
    return header + "\n" + "\n".join(lines).rstrip() + "\n"


RENDERERS = {
    "publications": render_publications,
    "datasets": render_datasets,
    "people": render_people,
}


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Refresh publications, datasets and contacts from ITU Pure.")
    ap.add_argument("feeds", nargs="*", default=[], metavar="FEED",
                    help="which feeds to refresh: %s (default: all)" % ", ".join(sorted(FEEDS)))
    ap.add_argument("--lang", default="en", choices=["en", "da"],
                    help="Pure portal language (default: en)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be written without touching files")
    ap.add_argument("--no-photos", action="store_true",
                    help="skip fetching portraits (one extra request per person); "
                         "everyone gets an initials monogram instead")
    args = ap.parse_args()

    unknown = [f for f in args.feeds if f not in FEEDS]
    if unknown:
        ap.error("unknown feed(s): %s. Choose from: %s"
                 % (", ".join(unknown), ", ".join(sorted(FEEDS))))

    selected = args.feeds or sorted(FEEDS)
    os.makedirs(OUT_DIR, exist_ok=True)

    failures = 0
    for name in selected:
        spec = FEEDS[name]
        url = BASE.format(lang=args.lang, section=spec["section"])
        dest = os.path.join(OUT_DIR, spec["out"])

        print("fetching %-13s %s" % (name, url))
        try:
            items = parse_items(fetch(url))
            if name == "people":
                markdown = render_people(items, url,
                                         want_photos=not args.no_photos,
                                         write=not args.dry_run)
            else:
                markdown = RENDERERS[name](items, url)
        except SystemExit as e:
            print("  %s" % e, file=sys.stderr)
            failures += 1
            continue

        if args.dry_run:
            print("  would write %d item(s), %d bytes -> %s"
                  % (len(items), len(markdown.encode("utf-8")),
                     os.path.relpath(dest, ROOT)))
            continue

        tmp = dest + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(markdown)
        os.replace(tmp, dest)
        print("  wrote %d item(s) -> %s" % (len(items), os.path.relpath(dest, ROOT)))

    if failures:
        print("\n%d feed(s) failed." % failures, file=sys.stderr)
        return 1
    print("\nDone. Reload the site to see the changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
