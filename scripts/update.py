#!/usr/bin/env python3
"""Refresh the brAIn lab site content from ITU's Pure research portal and LinkedIn.

Writes plain Markdown into content/data/:

    content/data/publications.md   <- pure.itu.dk/.../publications/?format=rss
    content/data/datasets.md       <- pure.itu.dk/.../datasets/?format=rss
    content/data/people.md         <- pure.itu.dk/.../persons/?format=rss
    content/data/news.md           <- linkedin.com/company/itu-brain-lab

Standard library only -- no pip install, no build step.

Usage:
    python3 scripts/update.py                 # every source, English portal
    python3 scripts/update.py --lang da       # use the Danish Pure portal
    python3 scripts/update.py news            # refresh one source only
    python3 scripts/update.py --dry-run

Note on datasets: the human-readable page at
https://pure.itu.dk/en/organisations/brain-lab/datasets/ sits behind a
Cloudflare browser challenge and cannot be scraped from a script. The
?format=rss view of that same listing is not challenged and carries the same
records, so that is what this script reads.

Note on news: LinkedIn publishes no feed for a company page, so the five
updates it renders for logged-out visitors are read off the page itself. A
repost that added no words of its own is unwrapped to the post it repeats --
see parse_update() -- so the news entry carries the original author, text,
photos, date and permalink rather than an empty shell.
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
    "news":         {"linkedin": True,          "out": "news.md"},
}

# The lab's LinkedIn page. dk.linkedin.com serves the same page with a Danish
# interface; parsing does not depend on the interface language, so either host
# works and only the page's own posts decide what ends up on the site.
LINKEDIN_URL = "https://www.linkedin.com/company/itu-brain-lab"

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

# Photos attached to a LinkedIn post, saved beside the hand-written news media
# for the same reason as the portraits: no hotlinking to a host we do not own.
NEWS_MEDIA_DIR = os.path.join(ROOT, "content", "media", "news")
NEWS_MEDIA_REL = "content/media/news"

# The author's picture beside each news byline. Kept in its own folder because
# it is keyed by author rather than by post: several updates share one file.
NEWS_AVATAR_DIR = os.path.join(NEWS_MEDIA_DIR, "authors")
NEWS_AVATAR_REL = NEWS_MEDIA_REL + "/authors"

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
        "Accept": "text/html, application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9,da;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            return res.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 403 and "pure.itu.dk" in url:
            raise SystemExit(
                "error: Pure returned 403 for %s\n"
                "       This usually means a Cloudflare challenge. Check that the URL\n"
                "       still ends in '?format=rss' -- the plain HTML views are blocked." % url
            )
        if e.code in (403, 429, 999):
            raise SystemExit(
                "error: HTTP %s fetching %s\n"
                "       LinkedIn rate-limits and occasionally walls off guest views.\n"
                "       Wait a while and try again; the other sources are unaffected."
                % (e.code, url)
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
# LinkedIn news
#
# The lab announces its news on LinkedIn, and LinkedIn renders a company
# page's five most recent updates for logged-out visitors. There is no feed
# and no public API for it, so the page itself is parsed. Everything below is
# written defensively -- a piece that has moved is dropped rather than fatal,
# because LinkedIn reshuffles this markup without notice.
# --------------------------------------------------------------------------

def element_slice(text, start, tag):
    """Return the substring covering the element that opens at `start`.

    A repost that added its own commentary nests an <article> inside an
    <article>, so a non-greedy regex would stop at the inner closing tag.
    Count the depth instead.
    """
    opener = re.compile(r"<%s\b" % tag)
    closer = re.compile(r"</%s\s*>" % tag)
    depth, pos = 0, start
    while pos < len(text):
        o = opener.search(text, pos)
        c = closer.search(text, pos)
        if not c:
            break
        if o and o.start() < c.start():
            depth += 1
            pos = o.end()
        else:
            depth -= 1
            pos = c.end()
            if depth == 0:
                return text[start:pos]
    return text[start:]


def split_updates(page):
    """Split the company page into one (card html, permalink) pair per update.

    The invisible overlay link that carries a post's permalink sits just
    before its card, so the gap since the previous card is where to look for
    it. Some cards ship without one; those fall back to a URL built from the
    activity id.
    """
    cards, prev_end = [], 0
    for m in re.finditer(r'<article\b[^>]*data-id="main-feed-card"', page):
        card = element_slice(page, m.start(), "article")
        link = re.search(r'href="([^"]+)"[^>]*data-id="main-feed-card__full-link"',
                         page[prev_end:m.start()])
        cards.append((card, html.unescape(link.group(1)) if link else ""))
        prev_end = m.start() + len(card)
    return cards


def urn_id(urn):
    """'urn:li:activity:7389783958345027584' -> '7389783958345027584'."""
    urn = urn or ""
    return urn.rsplit(":", 1)[-1] if urn.startswith("urn:") else ""


def urn_date(activity_id):
    """LinkedIn activity ids carry their creation time in the top 41 bits.

    The guest page only prints relative ages ('2mo'), which say nothing in a
    file regenerated at unpredictable intervals, so the real timestamp is
    recovered from the id instead.
    """
    try:
        stamp = int(activity_id) >> 22
    except (TypeError, ValueError):
        return None
    if not 1000000000000 < stamp < 4000000000000:     # sanity: roughly 2001-2096
        return None
    return datetime.fromtimestamp(stamp / 1000, timezone.utc)


def post_url(activity_id, permalink=""):
    if permalink:
        return permalink.split("?")[0]
    if activity_id:
        return "https://www.linkedin.com/feed/update/urn:li:activity:%s/" % activity_id
    return ""


LNKD_CACHE = {}


def expand_link(url, follow=True):
    """Unwrap a link out of LinkedIn's markup, or return '' to drop it.

    Outbound links arrive wrapped three different ways: a /redir/redirect hop,
    a lnkd.in shortener, and -- for hashtags and mentions shown to logged-out
    readers -- a /signup/cold-join wall. The first two are unwrapped so the
    news page points at the real page; the sign-up wall is dropped and only
    its label survives.
    """
    url = html.unescape(url or "").strip()
    if not url:
        return ""
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return ""

    if "/signup/cold-join" in parts.path or "/signup/" in parts.path:
        return ""

    if parts.path.startswith("/redir/redirect"):
        target = urllib.parse.parse_qs(parts.query).get("url", [""])[0]
        return expand_link(target, follow) if target else ""

    if parts.netloc.endswith("lnkd.in") and follow:
        # the shortener serves an interstitial page rather than a redirect
        if url not in LNKD_CACHE:
            page = try_fetch(url) or ""
            target = (first_group(r'data-tracking-control-name="external_url_click"[^>]*href="([^"]+)"', page)
                      or first_group(r'href="([^"]+)"[^>]*data-tracking-control-name="external_url_click"', page))
            LNKD_CACHE[url] = html.unescape(target) if target else url
        return LNKD_CACHE[url]

    # drop LinkedIn's click-tracking parameter, keep any real query string
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
             if k != "trk"]
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), ""))


def pretty_url(url, limit=60):
    """A long URL used as its own link text, shortened to something readable."""
    parts = urllib.parse.urlsplit(url)
    shown = (parts.netloc + parts.path).rstrip("/")
    return shown if len(shown) <= limit else shown[:limit].rstrip("/-_") + "…"


def plain_text(fragment):
    """Strip tags but keep the line breaks -- post bodies are pre-wrapped."""
    text = re.sub(r"<br\s*/?>", "\n", fragment or "")
    text = re.sub(r"</p\s*>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def news_escape(text):
    """md_escape, plus the characters that only start markup at a line start."""
    return re.sub(r"^(\s*)([#>=+-]|\d+\.)", r"\1\\\2", md_escape(text), flags=re.M)


def post_markdown(fragment, follow_links=True):
    """Turn a post body into Markdown, keeping its links and its line breaks.

    Links are stashed behind placeholders first so that escaping the prose
    around them cannot reach inside a URL.
    """
    links = []

    def stash(match):
        anchor = match.group(0)
        label = plain_text(anchor)
        url = expand_link(first_group(r'href="([^"]*)"', anchor), follow_links)
        if url and label:
            # a shortlink printed as its own label would contradict the href
            if url != label and re.match(r"https?://(?:www\.)?lnkd\.in/", label):
                label = pretty_url(url)
            links.append("[%s](%s)" % (md_escape(label), url))
        else:
            # a hashtag or mention behind the sign-up wall: keep the words only
            links.append(("\\" if label.startswith("#") else "") + md_escape(label))
        return "\x00%d\x00" % (len(links) - 1)

    text = news_escape(plain_text(re.sub(r"<a\b[^>]*>.*?</a>", stash, fragment or "", flags=re.S)))
    text = re.sub(r"\x00(\d+)\x00", lambda m: links[int(m.group(1))], text)
    # a lone newline is a deliberate line break in a post, but Markdown would
    # fold it into the paragraph -- ask for a hard break instead
    return re.sub(r"(?<!\n)\n(?!\n)", "  \n", text)


def undecorate(line):
    """Markdown back to the bare words, for use as a heading."""
    line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)     # links -> their label
    line = re.sub(r"\\(.)", r"\1", line)                     # drop escapes
    return re.sub(r"\s+", " ", line).strip()


def headline(text, limit=88):
    """A LinkedIn post has no title, so make one out of its opening line.

    Returns (title, body). When the whole first line became the title it is
    taken out of the body, rather than printed twice.
    """
    if not text.strip():
        return "", ""
    first, _, rest = text.partition("\n")
    title = undecorate(first)
    if len(title) <= limit:
        return title.rstrip(" -–—:"), rest.lstrip("\n")

    cut = title[:limit]
    stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if stop > limit // 2:
        return cut[:stop + 1].strip(), text
    space = cut.rfind(" ")
    return (cut[:space] if space > limit // 2 else cut).rstrip(" ,;:-–—") + "…", text


def save_news_image(url, name, want_photos, write=True):
    """Download one post image next to the hand-written news media."""
    if not want_photos:
        return ""
    if not write:
        return "%s/%s.jpg" % (NEWS_MEDIA_REL, name)     # --dry-run: report, do not fetch

    blob = try_fetch(url, binary=True)
    if not blob or len(blob) < 1024:
        return ""
    if blob[:2] == b"\xff\xd8":
        ext = ".jpg"
    elif blob[:8] == b"\x89PNG\r\n\x1a\n":
        ext = ".png"
    else:
        return ""                                      # an error page, not a photo

    os.makedirs(NEWS_MEDIA_DIR, exist_ok=True)
    with open(os.path.join(NEWS_MEDIA_DIR, name + ext), "wb") as fh:
        fh.write(blob)
    return "%s/%s%s" % (NEWS_MEDIA_REL, name, ext)


def profile_slug(profile, name):
    """A filename for an author: 'https://.../in/burelli' -> 'burelli'.

    Company and school pages use the same shape ('/company/itu-brain-lab'), and
    an author with no profile link at all falls back to their display name.
    """
    m = re.search(r"/(?:in|company|school|showcase)/([^/?#]+)",
                  urllib.parse.unquote(profile or ""))
    return ascii_slug(m.group(1)) if m else (ascii_slug(name) or "author")


AVATAR_CACHE = {}


def save_avatar(name, url, slug, want_photos, write=True):
    """Return a site-relative path to this author's picture.

    Same bargain as the portraits on the people page: the picture is copied
    here rather than hotlinked from media.licdn.com, and an author whose
    picture is missing or unreadable gets an initials monogram so that no
    byline ends up without one.
    """
    if slug in AVATAR_CACHE:
        return AVATAR_CACHE[slug]

    if not write:
        # --dry-run: report the path the monogram would take, write nothing
        AVATAR_CACHE[slug] = "%s/%s.svg" % (NEWS_AVATAR_REL, slug)
        return AVATAR_CACHE[slug]

    os.makedirs(NEWS_AVATAR_DIR, exist_ok=True)
    rel = ""

    if want_photos and url:
        blob = try_fetch(url, binary=True)
        if blob and len(blob) > 512:
            ext = ".jpg" if blob[:2] == b"\xff\xd8" else \
                  ".png" if blob[:8] == b"\x89PNG\r\n\x1a\n" else ""
            if ext:
                with open(os.path.join(NEWS_AVATAR_DIR, slug + ext), "wb") as fh:
                    fh.write(blob)
                rel = "%s/%s%s" % (NEWS_AVATAR_REL, slug, ext)

    if not rel:
        with open(os.path.join(NEWS_AVATAR_DIR, slug + ".svg"), "w", encoding="utf-8") as fh:
            fh.write(monogram(name, slug))
        rel = "%s/%s.svg" % (NEWS_AVATAR_REL, slug)

    AVATAR_CACHE[slug] = rel
    return rel


def card_actor(fragment, key=""):
    """The name, profile and picture behind a card's byline."""
    anchor = first_group(
        r'(<a\b[^>]*data-tracking-control-name='
        r'"organization_guest_main-feed-card%s_feed-actor-name".*?</a>)' % key, fragment)
    image = first_group(
        r'(<a\b[^>]*data-tracking-control-name='
        r'"organization_guest_main-feed-card%s_feed-actor-image".*?</a>)' % key, fragment)
    return (strip_tags(anchor),
            expand_link(first_group(r'href="([^"]*)"', anchor), follow=False),
            html.unescape(first_group(r'data-delayed-url="([^"]*)"', image)))


def card_body(fragment, commentary_id, follow_links=True):
    """The text, link preview and photos of one card."""
    preview_href = (first_group(r'<a\b[^>]*data-test-id="article-content"[^>]*href="([^"]*)"', fragment)
                    or first_group(r'<a\b[^>]*href="([^"]*)"[^>]*data-test-id="article-content"', fragment))
    gallery = first_group(r'data-test-id="feed-images-content"(.*?)</ul>', fragment)

    return {
        "text": post_markdown(first_group(r'data-test-id="%s"[^>]*>(.*?)</p>' % commentary_id,
                                          fragment), follow_links),
        "preview": {
            "url": expand_link(preview_href, follow_links),
            "title": strip_tags(first_group(
                r'data-test-id="article-content__title"[^>]*>(.*?)</span>', fragment)),
            "host": strip_tags(first_group(
                r'data-test-id="article-content__subtitle"[^>]*>(.*?)</span>', fragment)),
        },
        "images": [html.unescape(u) for u in re.findall(r'data-delayed-url="([^"]+)"', gallery)],
    }


def parse_update(card, permalink="", follow_links=True):
    """One update, with a pure repost resolved to the post it repeats.

    LinkedIn has two kinds of repost and they need opposite treatment:

      * A *pure* repost -- '... reposted this', nothing added -- is rendered as
        the original post itself: the byline is the original author and the
        body is their words. That original is the news, so it is what gets
        extracted, credited, dated and linked (via data-featured-activity-urn),
        and the lab's empty repost around it is dropped.

      * A repost *with* commentary keeps the lab's own words on top and nests
        the original in an inner <article>, which is carried through as a
        quotation underneath.
    """
    activity = urn_id(first_group(r'data-activity-urn="([^"]*)"', card))
    featured = urn_id(first_group(r'data-featured-activity-urn="([^"]*)"', card))

    inner = re.search(r'<article\b[^>]*feed-reshare-content', card)
    quoted_html = element_slice(card, inner.start(), "article") if inner else ""
    outer = card.replace(quoted_html, "") if quoted_html else card

    entry = card_body(outer, "main-feed-activity-card__commentary", follow_links)
    entry["author"], entry["profile"], entry["avatar_url"] = card_actor(outer)
    entry["pure_repost"] = "main-feed-activity-card__header" in outer and not quoted_html

    entry["quoted"] = None
    if quoted_html:
        quoted = card_body(quoted_html, "feed-reshare-content__commentary", follow_links)
        quoted["author"], quoted["profile"], quoted["avatar_url"] = \
            card_actor(quoted_html, "_reshare")
        entry["quoted"] = quoted

    entry["id"] = (featured or activity) if entry["pure_repost"] else activity
    entry["date"] = urn_date(entry["id"]) or urn_date(activity)
    entry["url"] = post_url(entry["id"], permalink)
    return entry


def media_lines(card, want_photos, write):
    """Photos, then the link preview -- app.js turns a video link into a player."""
    out = []
    shots = []
    for n, url in enumerate(card["images"], 1):
        rel = save_news_image(url, "%s-%d" % (card["key"], n), want_photos, write)
        if rel:
            shots.append("![](%s)" % rel)
    if shots:
        # one paragraph, so the page groups them into a single lightbox gallery
        out.append("%s\n" % "\n".join(shots))

    preview = card["preview"]
    if preview["url"]:
        out.append("[%s](%s)\n" % (md_escape(preview["title"] or preview["host"]
                                              or preview["url"]), preview["url"]))
    return out


def byline(card):
    return "[%s](%s)" % (md_escape(card["author"]), card["profile"]) if card["profile"] \
        else md_escape(card["author"])


def avatar_image(card, want_photos, write):
    """The author's picture, as a Markdown image on its own line.

    It sits directly above the credit line, in the same paragraph: that is the
    hook the stylesheet and the lightbox use to tell a byline avatar apart from
    a photo attached to the post -- an image whose next sibling is the credit.
    Alt is empty on purpose, because the name follows immediately.
    """
    if not (card["author"] or card["avatar_url"]):
        return ""
    rel = save_avatar(card["author"], card["avatar_url"],
                      profile_slug(card["profile"], card["author"]), want_photos, write)
    return "![](%s)\n" % rel if rel else ""


def quote_lines(quoted, want_photos, write):
    """The post a commented repost is quoting, rendered as one blockquote.

    Every line has to carry the marker, blank ones included: a truly blank line
    would close the quote and start a second one.
    """
    parts = []
    if quoted["author"]:
        parts.append("%s**%s**" % (avatar_image(quoted, want_photos, write), byline(quoted)))
    if quoted["text"]:
        parts.append(quoted["text"])
    parts.extend(chunk.strip("\n") for chunk in media_lines(quoted, want_photos, write))
    if not parts:
        return []
    block = "\n\n".join(parts)
    return ["%s\n" % "\n".join("> " + l if l.strip() else ">" for l in block.split("\n"))]


def news_entry_lines(entry, want_photos, write):
    title, body = headline(entry["text"])
    lines = ["## %s\n" % (title or "Update from the lab")]
    if entry["date"]:
        lines.append("*%s*\n" % entry["date"].strftime("%B %-d, %Y"))
    if body.strip():
        lines.append("%s\n" % body.strip())

    lines.extend(media_lines(entry, want_photos, write))
    if entry["quoted"]:
        lines.extend(quote_lines(entry["quoted"], want_photos, write))

    credit = []
    if entry["author"]:
        credit.append("Posted by %s" % byline(entry))
    if entry["url"]:
        credit.append("[view on LinkedIn](%s)" % entry["url"])
    if credit:
        lines.append("%s*%s*\n" % (avatar_image(entry, want_photos, write) if entry["author"]
                                   else "", " · ".join(credit)))
    return lines


def render_news(cards, source_url, want_photos=True, write=True, follow_links=True):
    lines, kept = [], 0
    for card, permalink in cards:
        entry = parse_update(card, permalink, follow_links)
        if not (entry["text"] or entry["images"] or entry["preview"]["url"] or entry["quoted"]):
            continue                                   # an empty shell: nothing to show
        entry["key"] = entry["id"] or ascii_slug(entry["author"]) or "post-%d" % (kept + 1)
        if entry["quoted"]:
            entry["quoted"]["key"] = entry["key"] + "-quoted"
        lines.extend(news_entry_lines(entry, want_photos, write))
        kept += 1
    return finish(lines, source_url, kept, "update")


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
}


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Refresh publications, datasets and people from ITU Pure, and news from LinkedIn.")
    ap.add_argument("feeds", nargs="*", default=[], metavar="FEED",
                    help="which feeds to refresh: %s (default: all)" % ", ".join(sorted(FEEDS)))
    ap.add_argument("--lang", default="en", choices=["en", "da"],
                    help="Pure portal language (default: en)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be written without touching files")
    ap.add_argument("--no-photos", action="store_true",
                    help="skip fetching images: portraits (one extra request per "
                         "person, everyone gets an initials monogram instead) and "
                         "the photos attached to LinkedIn posts")
    ap.add_argument("--linkedin-url", default=LINKEDIN_URL, metavar="URL",
                    help="company page to read the news from (default: %s)" % LINKEDIN_URL)
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
        url = args.linkedin_url if spec.get("linkedin") else \
            BASE.format(lang=args.lang, section=spec["section"])
        dest = os.path.join(OUT_DIR, spec["out"])

        print("fetching %-13s %s" % (name, url))
        try:
            if spec.get("linkedin"):
                items = split_updates(fetch(url))
                if not items:
                    raise SystemExit(
                        "error: no updates found on %s\n"
                        "       Either the page has none, or LinkedIn served a sign-in\n"
                        "       wall or changed its markup -- check split_updates()." % url)
                # --dry-run stays offline past the page itself: no photos saved
                # and no shortened links followed
                markdown = render_news(items, url,
                                       want_photos=not args.no_photos,
                                       write=not args.dry_run,
                                       follow_links=not args.dry_run)
            elif name == "people":
                items = parse_items(fetch(url))
                markdown = render_people(items, url,
                                         want_photos=not args.no_photos,
                                         write=not args.dry_run)
            else:
                items = parse_items(fetch(url))
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
