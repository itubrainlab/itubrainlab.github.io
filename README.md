# ITU brAIn lab — static site

A client-side rebuild of [brainlab.itu.dk](https://brainlab.itu.dk/), keeping the
original red-and-black palette (`#bc0020` on `#111`) and page structure.

Every page's text lives in a Markdown file under `content/`. There is no build
step, no bundler and no framework — one HTML shell, one stylesheet, one small
router script, and a vendored copy of [marked](https://marked.js.org/) to turn
Markdown into HTML in the browser.

## Running it

The pages are fetched with `fetch()`, so the site has to be served over HTTP —
opening `index.html` straight off disk will not work (the browser blocks
`file://` requests). Any static server does:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000/>.

To deploy, copy the whole folder to any static host (GitHub Pages, Netlify, an
ITU web share, an S3 bucket). Nothing needs to be compiled first.

## Layout

```
index.html                 page shell: header, nav, sidebar, footer
assets/css/style.css       the whole design
assets/js/app.js           hash router + Markdown loader (~200 lines)
assets/js/marked.min.js    vendored Markdown parser (MIT)
assets/img/                logo, favicon mark, team photo
assets/img/neural-bg.svg   faint synapse texture behind the page
assets/img/people/         GENERATED — portraits and initials monograms
content/
  about.md                 "About the lab"        (#/about)
  thesis.md                "Thesis Project Ideas" (#/thesis)
  contacts.md              "Contacts"             (#/contacts)
  publications.md          "Publications"         (#/publications)
  datasets.md              "Datasets"             (#/datasets)
  news.md                  "News"                 (#/news)
  data/                    GENERATED — do not edit by hand
    publications.md
    datasets.md
    people.md
scripts/update.py          refreshes content/data/ from ITU Pure
scripts/make_background.py regenerates the neural background SVG
```

## The background texture

`assets/img/neural-bg.svg` is a faint neuron graph — nodes wired to their
nearest neighbours with slightly bowed connections. It is fixed to the viewport
behind the content, so it stays put while the page scrolls and never tiles, and
it is hidden when printing.

Three things move:

- **Discharges arc along the connections.** This is the effect you actually
  notice. Four things together make it read as electricity rather than as a dot
  sliding down a wire:
  - each discharge is drawn **twice** — a wide, faint halo (5px, 5%) with a
    narrower, brighter core (1.5px, 10%) on top of it, which gives a glow
    without needing an SVG blur filter;
  - the core carries a **second animation** on its own clock, guttering its
    `stroke-opacity` on an uneven 2s cycle so it does not glide at a steady
    brightness. A discharge is only lit for a second or two, so most get through
    just a step or two of that cycle — the unsteadiness is slow, not a strobe.
    The two animations coexist because they touch different properties —
    `opacity` for the dart, `stroke-opacity` for the flicker — so neither
    overwrites the other;
  - a connection is only lit for **30% of its cycle** (`SIGNAL_DART`) and dark
    the rest, so the network fires in bursts rather than running like a conveyor
    belt. Roughly 10 of the 37 are lit at any moment;
  - the flicker period is deliberately **not a factor of** the dart period, so a
    given connection never strobes the same way twice.

  Each path carries `pathLength="100"`, which normalises paths of different real
  lengths so a single `stroke-dashoffset` keyframe drives all of them.
- **Neurons pulse** between 25% and full strength over 5–11s.
- **The whole graph drifts** 8px over 90 seconds.

Every animated element gets a random negative animation delay, so nothing moves
in unison and the page never opens on a synchronised flash. Under
`prefers-reduced-motion: reduce` the discharges are hidden outright rather than
frozen mid-connection, and the graph itself stops moving.

A note if you tune this: the node pulse on its own is not perceptible. The nodes
rest at around 7% opacity, so pulsing them still only swings between roughly
0.02 and 0.07 alpha on white — real, measurable, and invisible. The discharges
read because the core is drawn at a couple of times the opacity of the resting
connections underneath it *and* because it moves; opacity alone is not what
makes them visible.

**Why app.js injects it instead of using `background-image`:** browsers freeze
CSS animations inside an SVG that is used as a CSS background — the image
renders, but permanently at frame 0. The animation only runs when the SVG is
inline in the DOM, so `mountBackground()` fetches the file and drops it into
`<div class="neural-bg">`. It is decorative, so if that fetch fails the page
carries on without it.

The SVG is committed, so nothing needs to run for the site to work. The dials
are near the top of `scripts/make_background.py`:

| Setting | Controls |
|---|---|
| `EDGE_OPACITY`, `NODE_OPACITY` | how visible the resting graph is |
| `SIGNAL_SHARE` | how many connections carry a discharge |
| `SIGNAL_MIN`, `SIGNAL_MAX` | seconds for one fire-and-rest cycle |
| `SIGNAL_DART` | fraction of that cycle spent lit — lower means rarer, snappier bursts |
| `CORE_*`, `HALO_*` | width, length and opacity of the bolt and its glow |
| `FLICKER_SECONDS` | how fast the core gutters |
| `SIGNAL_ACCENT_SHARE` | how many discharges run red rather than black |
| `FIRING_SHARE`, `PULSE_MIN`, `PULSE_MAX`, `PULSE_DIM` | the node pulse |
| `DRIFT_SECONDS`, `DRIFT_PX` | the slow drift of the whole graph |

Set `SIGNAL_SHARE = 0` and `FIRING_SHARE = 0` for a completely static image.
Re-run after editing:

```bash
python3 scripts/make_background.py
```

The random seed is fixed, so the same settings always redraw the same picture.

## Editing content

Edit the Markdown in `content/` and reload the page. Each file starts with a
small front-matter block:

```markdown
---
title: About the lab
sidebar: news
---
```

- `title` — the `<h1>` and the browser tab title.
- `sidebar` — `news` shows the News widget beside the content, anything else
  (or omitting it) gives a full-width page.

A page can pull in another Markdown file with an include directive:

```markdown
{{include: content/data/publications.md}}
```

The included file is rendered separately and wrapped in a `.record-list`
container, which is how the Pure-generated lists get their own styling without
affecting the surrounding prose.

### Embedding a video

Put a YouTube or Vimeo link **alone on its own line** and it becomes a player:

```markdown
[Watch the video](https://youtu.be/XDGEcByv-N0)
```

A link inside a sentence is left as a link — only a paragraph that contains
nothing but the link is converted, so prose that happens to cite a video is not
disturbed. `embedVideos()` in `app.js` does the swap after Markdown rendering;
there is no special syntax to learn and the Markdown still reads fine as text.

Recognised: `youtu.be/ID`, `youtube.com/watch?v=ID`, `/embed/`, `/shorts/`, and
`vimeo.com/ID`. A `?t=` start time is carried over (`90` or `1m30s` both work).
YouTube embeds use `youtube-nocookie.com` so viewers are not tracked before they
press play. Players are 16:9 and capped at 760px wide.

### Adding a page

1. Create `content/yourpage.md` with front matter.
2. Add a line to `ROUTES` in `assets/js/app.js`.
3. Add a `<li><a href="#/yourpage">…</a></li>` to the nav in `index.html`.
   The desktop nav needs about 911px for its six items and switches to the
   mobile menu at 940px, so there is little room for another one before that
   breakpoint needs raising.

### Adding news

Append a `## Title` section to `content/news.md`, with the date on the next
line as `*April 10, 2025*`. The sidebar widget picks up the five most recent
entries automatically and links to them.

## Updating publications, datasets and contacts

```bash
python3 scripts/update.py
```

Standard library only — no `pip install`. It reads three RSS feeds from ITU's
Pure portal and rewrites the three files in `content/data/`:

| File | Source |
|---|---|
| `content/data/publications.md` | `pure.itu.dk/en/organisations/brain-lab/publications/?format=rss` |
| `content/data/datasets.md` | `pure.itu.dk/en/organisations/brain-lab/datasets/?format=rss` |
| `content/data/people.md` | `pure.itu.dk/en/organisations/brain-lab/persons/?format=rss` |

Options:

```bash
python3 scripts/update.py --dry-run          # show what would change
python3 scripts/update.py publications       # one feed only
python3 scripts/update.py --lang da          # Danish Pure portal instead of English
python3 scripts/update.py --no-photos        # skip fetching portraits
```

Publications are grouped by year. Email addresses on the people list come out
of Pure's base64 obfuscation and are written as ordinary `mailto:` links.

### Portraits

The person feed carries no images, so the script also fetches each person's Pure
page, pulls the portrait out of it, and saves it to `assets/img/people/`. The
site therefore serves its own copies rather than hotlinking `pure.itu.dk` on
every page view.

Most people have no portrait uploaded to Pure — at the time of writing only two
of eight do. Everyone else gets a generated initials monogram (an SVG in the
same folder) so the contacts list stays visually even instead of mixing photos
with ragged text-only rows. Upload a portrait to Pure and the next run replaces
that person's monogram with the real thing.

Filenames are folded to plain ASCII: Pure slugs can contain non-ASCII characters
(`morten-ib-kj%C3%A6rgaard-munk`), and keeping those in filenames means URL
escaping plus a macOS/Linux Unicode-normalisation mismatch waiting to happen.

`--no-photos` skips the portrait fetch — it costs one extra request per person —
and gives everybody a monogram. `--dry-run` writes no image files at all.

### Who counts as a lab coordinator

The people list is split into **Lab Coordinators** and **Lab Members**. The
coordinators are named in the `COORDINATORS` constant at the top of
`scripts/update.py`:

```python
COORDINATORS = [
    {"slug": "stefan-heinrich", "name": "Stefan Heinrich"},
    {"slug": "paolo-burelli",   "name": "Paolo Burelli"},
]
```

Each entry matches on the Pure person-page slug first and falls back to the
display name, so neither a renamed slug nor a changed display name silently
drops someone into Lab Members. Coordinators appear in the order listed above;
everyone else keeps the order Pure returned. A group whose people are all absent
from the feed is omitted rather than left as an empty heading — so if Pure stops
listing both coordinators, the page is simply a Lab Members list.

To change who is a coordinator, edit that constant and re-run the script.

**On the datasets source:** the human-readable listing at
`pure.itu.dk/en/organisations/brain-lab/datasets/` is behind a Cloudflare
browser challenge and returns 403 to any script. The `?format=rss` view of the
same listing is not challenged and carries the same records, so the script
reads that instead.

**On `--lang`:** the feeds default to the English portal, so record types read
"Research output: Theses › PhD thesis" and "Dataset". Run with `--lang da` for
the Danish portal instead ("Publikation: Afhandlinger › Ph.d.-afhandling",
"Datasæt"); note that it also changes the `pure.itu.dk/...` links in the
generated files.

## Notes

- The News content was carried over from the original WordPress site; it is
  static Markdown and is not touched by `update.py`.
- `assets/js/marked.min.js` is the only third-party file. Replacing it means
  swapping one `<script>` tag.
