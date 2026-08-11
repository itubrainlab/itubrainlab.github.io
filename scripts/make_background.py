#!/usr/bin/env python3
"""Regenerate assets/img/neural-bg.svg — the faint synapse texture behind the page.

The site does not need this to run; the SVG is committed. Re-run it only to
change the look, then reload the site.

    python3 scripts/make_background.py

The seed is fixed, so the same settings always produce the same picture.
Turn EDGE_OPACITY / NODE_OPACITY up to make the texture more visible.
"""

import math
import os
import random

W, H = 1600, 1000
SEED = 20240611          # lab opening date, so runs are reproducible
COUNT = 52               # target number of neurons
MIN_DIST = 108           # keeps the scatter even instead of clumpy
MAX_EDGE = 300           # no connections clear across the canvas

EDGE_OPACITY = 0.040     # the whole point is that these are barely there
NODE_OPACITY = 0.070     # animated nodes spend most of their time below this
ACCENT_OPACITY = 0.088
ACCENT_SHARE = 0.17      # fraction of neurons picking up the brand red

# Animation. Two effects: neurons pulse in brightness, and signals travel along
# a subset of the connections. Everything is staggered by a random negative
# delay so nothing moves in unison. Set FIRING_SHARE and SIGNAL_SHARE to 0 for
# a static image.
FIRING_SHARE = 0.60      # fraction of neurons that pulse at all
PULSE_MIN, PULSE_MAX = 5, 11     # seconds for one pulse cycle
PULSE_DIM = 0.25         # how far down a pulse dips, as a fraction of full
DRIFT_SECONDS = 90       # one full there-and-back drift of the whole graph
DRIFT_PX = 8

# Travelling signals — the discharges arcing along the connections. These are
# what actually read as movement; a node pulse alone is too small a change in
# alpha to notice. Each is drawn twice: a wide soft halo for the glow and a
# narrow bright core on top, both riding the same dash animation.
# pathLength="100" normalises every path so one keyframe fits all of them
# regardless of their real length.
SIGNAL_SHARE = 0.42      # fraction of connections that carry a discharge
SIGNAL_MIN, SIGNAL_MAX = 3.5, 8.0    # seconds for one full fire-and-rest cycle
SIGNAL_DART = 0.30       # fraction of that cycle spent actually travelling;
                         # the rest is dark, so connections fire in bursts
                         # instead of running like a conveyor belt
SIGNAL_ACCENT_SHARE = 0.62   # most discharges run hot in the brand red

CORE_DASH = 4            # bright head, in the normalised 0-100 path space
CORE_WIDTH = 1.5
CORE_OPACITY = 0.1      # peak; the flicker keyframes swing around this
HALO_DASH = 11           # longer + wider + fainter = bloom around the head
HALO_WIDTH = 5.0
HALO_OPACITY = 0.05
FLICKER_SECONDS = 2.0    # slow, unsteady guttering on the core. A discharge is
                         # only lit for a second or two, so at this period most
                         # get through just a step or two of it.

INK = "#111111"
ACCENT = "#bc0020"

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "assets", "img", "neural-bg.svg")


def main():
    rng = random.Random(SEED)

    # scatter neurons by rejection sampling
    pts, tries = [], 0
    while len(pts) < COUNT and tries < 40000:
        tries += 1
        p = (rng.uniform(40, W - 40), rng.uniform(40, H - 40))
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 > MIN_DIST ** 2 for q in pts):
            pts.append(p)

    def dist(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    # wire each neuron to its 2-3 nearest neighbours
    edges = set()
    for i, p in enumerate(pts):
        near = sorted(range(len(pts)), key=lambda j: dist(p, pts[j]))[1:4]
        for j in near[:rng.choice([2, 2, 3])]:
            if dist(p, pts[j]) < MAX_EDGE:
                edges.add((min(i, j), max(i, j)))

    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
           'preserveAspectRatio="xMidYMid slice" width="%d" height="%d">' % (W, H, W, H)]

    # Animation lives inside the SVG so the file animates on its own when opened
    # directly. Note browsers freeze it at frame 0 when an SVG is used as a CSS
    # background-image, which is why app.js injects this into the DOM instead.
    # Class and keyframe names are namespaced because an inline SVG's <style>
    # applies to the whole document, not just the SVG.
    dart = SIGNAL_DART * 100
    css = {
        "dim": PULSE_DIM,
        "driftx": DRIFT_PX,
        "drifty": DRIFT_PX - 3,
        "driftsec": DRIFT_SECONDS,
        "fade": "%.0f" % max(dart - 4, 3),   # hold full opacity until just
        "dart": "%.0f" % dart,               # before the head lands
        "core": CORE_OPACITY,
        "arcdim": CORE_OPACITY * 0.45,
        "archot": CORE_OPACITY * 1.25,
        "flicker": FLICKER_SECONDS,
    }
    out.append((
        '<style>\n'
        '  @keyframes nbg-fire { 0%%, 100%% { opacity: %(dim).2f } 50%% { opacity: 1 } }\n'
        '  @keyframes nbg-drift {\n'
        '    0%%, 100%% { transform: translate(0, 0) }\n'
        '    50%% { transform: translate(-%(driftx)dpx, %(drifty)dpx) }\n'
        '  }\n'
        '  /* A discharge: darts the length of the path, then the connection\n'
        '     sits dark for the rest of the cycle. */\n'
        '  @keyframes nbg-signal {\n'
        '    0%%          { stroke-dashoffset: 100; opacity: 0 }\n'
        '    2%%          { opacity: 1 }\n'
        '    %(fade)s%%   { opacity: 1 }\n'
        '    %(dart)s%%   { stroke-dashoffset: 0; opacity: 0 }\n'
        '    100%%        { stroke-dashoffset: 0; opacity: 0 }\n'
        '  }\n'
        '  /* uneven, so the core reads as an arc rather than a clean tracer */\n'
        '  @keyframes nbg-arc {\n'
        '    0%%, 100%% { stroke-opacity: %(core).3f }\n'
        '    14%%       { stroke-opacity: %(arcdim).3f }\n'
        '    22%%       { stroke-opacity: %(archot).3f }\n'
        '    39%%       { stroke-opacity: %(arcdim).3f }\n'
        '    56%%       { stroke-opacity: %(core).3f }\n'
        '    68%%       { stroke-opacity: %(arcdim).3f }\n'
        '    83%%       { stroke-opacity: %(archot).3f }\n'
        '  }\n'
        '  .nbg-net { animation: nbg-drift %(driftsec)ds ease-in-out infinite; }\n'
        '  .nbg-fires {\n'
        '    animation-name: nbg-fire;\n'
        '    animation-timing-function: ease-in-out;\n'
        '    animation-iteration-count: infinite;\n'
        '  }\n'
        '  .nbg-signal {\n'
        '    animation-name: nbg-signal;\n'
        '    animation-timing-function: linear;\n'
        '    animation-iteration-count: infinite;\n'
        '  }\n'
        '  /* the core carries the dart AND a fast flicker; they touch different\n'
        '     properties (opacity vs stroke-opacity) so they do not fight */\n'
        '  .nbg-core {\n'
        '    animation-name: nbg-signal, nbg-arc;\n'
        '    animation-timing-function: linear, steps(1, end);\n'
        '    animation-iteration-count: infinite, infinite;\n'
        '  }\n'
        '  @media (prefers-reduced-motion: reduce) {\n'
        '    .nbg-net, .nbg-fires { animation: none }\n'
        '    .nbg-signal, .nbg-core { display: none }\n'
        '  }\n'
        '</style>') % css)

    out.append('<g class="nbg-net">')
    out.append('<g fill="none" stroke="%s" stroke-opacity="%.3f" stroke-width="1">'
               % (INK, EDGE_OPACITY))

    geometry = []
    for i, j in sorted(edges):
        (x1, y1), (x2, y2) = pts[i], pts[j]
        # bow each axon slightly so the graph reads organic, not like a wireframe
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1
        k = rng.uniform(-0.10, 0.10) * length
        cx, cy = mx - dy / length * k, my + dx / length * k
        d = "M%.1f %.1f Q%.1f %.1f %.1f %.1f" % (x1, y1, cx, cy, x2, y2)
        geometry.append(d)
        out.append('<path d="%s"/>' % d)
    out.append('</g>')

    # Discharges, drawn over the resting connections. Halo first so the bright
    # core sits on top of its own glow.
    out.append('<g fill="none" stroke-linecap="round">')
    signals = 0
    for d in geometry:
        if rng.random() >= SIGNAL_SHARE:
            continue
        signals += 1
        period = rng.uniform(SIGNAL_MIN, SIGNAL_MAX)
        delay = rng.uniform(0, period)
        colour = ACCENT if rng.random() < SIGNAL_ACCENT_SHARE else INK
        timing = 'animation-duration:%.2fs;animation-delay:-%.2fs' % (period, delay)

        out.append('<path d="%s" pathLength="100" class="nbg-signal" stroke="%s" '
                   'stroke-opacity="%.3f" stroke-width="%.1f" stroke-dasharray="%d %d" '
                   'style="%s"/>'
                   % (d, colour, HALO_OPACITY, HALO_WIDTH, HALO_DASH, 100 - HALO_DASH,
                      timing))
        # The flicker runs on its own clock, deliberately not a factor of the
        # dart period, so the core never strobes the same way twice.
        out.append('<path d="%s" pathLength="100" class="nbg-core" stroke="%s" '
                   'stroke-width="%.1f" stroke-dasharray="%d %d" '
                   'style="%s,%.2fs;animation-delay:-%.2fs,-%.2fs"/>'
                   % (d, colour, CORE_WIDTH, CORE_DASH, 100 - CORE_DASH,
                      'animation-duration:%.2fs' % period, FLICKER_SECONDS,
                      delay, rng.uniform(0, FLICKER_SECONDS)))
    out.append('</g>')

    out.append('<g stroke="none">')
    for x, y in pts:
        big = rng.random() < 0.22
        r = rng.uniform(5.0, 7.5) if big else rng.uniform(2.4, 3.8)
        accent = rng.random() < ACCENT_SHARE
        fill = ACCENT if accent else INK
        op = ACCENT_OPACITY if accent else NODE_OPACITY

        # A negative delay starts each pulse mid-cycle, so nothing is
        # synchronised and the page never opens on a uniform flash.
        if rng.random() < FIRING_SHARE:
            period = rng.uniform(PULSE_MIN, PULSE_MAX)
            anim = (' class="nbg-fires" style="animation-duration:%.1fs;'
                    'animation-delay:-%.1fs"' % (period, rng.uniform(0, period)))
        else:
            anim = ''

        out.append('<g%s>' % anim)
        out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" fill-opacity="%.3f"/>'
                   % (x, y, r, fill, op))
        if big:      # a soft halo on the larger somas
            out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" '
                       'stroke-opacity="%.3f" stroke-width="1"/>' % (x, y, r + 5, fill, op * 0.6))
        out.append('</g>')
    out.append('</g></g></svg>')

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print("wrote %s — %d neurons, %d connections, %d carrying signals"
          % (os.path.relpath(OUT), len(pts), len(edges), signals))


if __name__ == "__main__":
    main()
