/* ITU brAIn lab — tiny hash router that renders Markdown files.
   No build step, no framework: the only dependency is marked.js (vendored). */

(function () {
  'use strict';

  var ROUTES = {
    about:        { file: 'content/about.md',        title: 'About the lab' },
    thesis:       { file: 'content/thesis.md',       title: 'Thesis Project Ideas' },
    contacts:     { file: 'content/contacts.md',     title: 'Contacts' },
    publications: { file: 'content/publications.md', title: 'Publications' },
    datasets:     { file: 'content/datasets.md',     title: 'Datasets' },
    news:         { file: 'content/news.md',         title: 'News' }
  };

  var DEFAULT_ROUTE = 'about';
  var NEWS_FILE = 'content/news.md';
  var BACKGROUND_FILE = 'assets/img/neural-bg.svg';
  var SIDEBAR_NEWS_COUNT = 5;

  var els = {
    title:   document.getElementById('page-title'),
    content: document.getElementById('page-content'),
    sidebar: document.getElementById('sidebar'),
    news:    document.getElementById('news-list'),
    wrapper: document.querySelector('.page-wrapper'),
    menu:    document.getElementById('nav-menu'),
    toggle:  document.getElementById('nav-toggle')
  };

  var cache = {};

  marked.setOptions({ gfm: true, breaks: false, headerIds: false, mangle: false });

  /* ---------- helpers ---------- */

  function slugify(s) {
    return String(s).toLowerCase()
      .replace(/[‘’']/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  function fetchText(path) {
    if (cache[path]) return cache[path];
    cache[path] = fetch(path, { cache: 'no-cache' }).then(function (res) {
      if (!res.ok) throw new Error(res.status + ' ' + res.statusText + ' — ' + path);
      return res.text();
    });
    return cache[path];
  }

  /* Split off a leading `---` frontmatter block. Supports `key: value` only. */
  function parseFrontMatter(text) {
    var meta = {};
    var m = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(text);
    if (!m) return { meta: meta, body: text };
    m[1].split(/\r?\n/).forEach(function (line) {
      var i = line.indexOf(':');
      if (i > 0) meta[line.slice(0, i).trim()] = line.slice(i + 1).trim();
    });
    return { meta: meta, body: text.slice(m[0].length) };
  }

  /* Resolve `{{include: path.md}}` directives.
     Each include is rendered on its own and wrapped in .record-list so the
     Pure-generated files can be styled independently of the page prose. */
  function renderWithIncludes(body) {
    var parts = body.split(/\{\{\s*include:\s*([^}|]+?)\s*(?:\|\s*([^}]+?)\s*)?\}\}/g);
    var jobs = [];

    for (var i = 0; i < parts.length; i += 3) {
      jobs.push(Promise.resolve(marked.parse(parts[i])));
      if (i + 1 < parts.length) {
        jobs.push(includeJob(parts[i + 1], parts[i + 2] || 'record-list'));
      }
    }
    return Promise.all(jobs).then(function (chunks) { return chunks.join('\n'); });
  }

  function includeJob(path, cls) {
    return fetchText(path).then(function (text) {
      var inner = marked.parse(parseFrontMatter(text).body);
      return '<div class="' + cls + '">' + inner + '</div>';
    }).catch(function (err) {
      return '<p class="error">Could not load <code>' + path + '</code>. ' +
             'Run <code>python3 scripts/update.py</code> to generate it.</p>';
    });
  }

  /* Split a news Markdown file into entries on `## ` headings. */
  function parseNews(text) {
    var body = parseFrontMatter(text).body;
    var entries = [];
    var re = /^##\s+(.+)$/gm;
    var matches = [];
    var m;
    while ((m = re.exec(body)) !== null) matches.push({ title: m[1].trim(), start: m.index, end: re.lastIndex });

    matches.forEach(function (cur, i) {
      var next = matches[i + 1];
      var chunk = body.slice(cur.end, next ? next.start : body.length);
      var dateMatch = /^\s*\*([^*]+)\*\s*$/m.exec(chunk);
      entries.push({
        title: cur.title,
        slug: slugify(cur.title),
        date: dateMatch ? dateMatch[1].trim() : ''
      });
    });
    return entries;
  }

  function renderNewsSidebar() {
    return fetchText(NEWS_FILE).then(function (text) {
      var entries = parseNews(text).slice(0, SIDEBAR_NEWS_COUNT);
      els.news.innerHTML = entries.map(function (e) {
        return '<li><a class="news-title" href="#/news?e=' + encodeURIComponent(e.slug) + '">' +
               escapeHtml(e.title) + '</a>' +
               (e.date ? '<span class="news-date">' + escapeHtml(e.date) + '</span>' : '') +
               '</li>';
      }).join('');
    }).catch(function () {
      els.news.innerHTML = '<li class="error">News could not be loaded.</li>';
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  /* ---------- routing ---------- */

  function currentRoute() {
    var raw = location.hash.replace(/^#\/?/, '');
    var qi = raw.indexOf('?');
    var query = qi >= 0 ? raw.slice(qi + 1) : '';
    var name = (qi >= 0 ? raw.slice(0, qi) : raw).replace(/\/$/, '');
    if (!ROUTES[name]) name = DEFAULT_ROUTE;
    return { name: name, query: new URLSearchParams(query) };
  }

  function setActiveNav(name) {
    els.menu.querySelectorAll('a').forEach(function (a) {
      a.classList.toggle('active', a.getAttribute('href') === '#/' + name);
    });
  }

  function render() {
    var route = currentRoute();
    var def = ROUTES[route.name];

    setActiveNav(route.name);
    els.menu.classList.remove('open');
    els.toggle.setAttribute('aria-expanded', 'false');

    return fetchText(def.file).then(function (text) {
      var parsed = parseFrontMatter(text);
      var title = parsed.meta.title || def.title;

      document.title = title + ' — ITU brAIn lab';
      els.title.textContent = title;

      var showSidebar = parsed.meta.sidebar === 'news';
      els.sidebar.hidden = !showSidebar;
      els.wrapper.classList.toggle('no-sidebar', !showSidebar);

      // lets the stylesheet target one page without extra markup in the content
      els.content.dataset.page = route.name;

      return renderWithIncludes(parsed.body).then(function (html) {
        els.content.innerHTML = html;
        // a news gallery can be a dozen photos; do not block the page on them
        els.content.querySelectorAll('img').forEach(function (img) {
          img.loading = 'lazy';
          img.decoding = 'async';
        });
        embedVideos();
        decorateExternalLinks();
        if (route.name === 'news') tagNewsEntries();
        scrollToTarget(route.query.get('e'));
      });
    }).catch(function (err) {
      els.sidebar.hidden = true;
      els.wrapper.classList.add('no-sidebar');
      els.title.textContent = 'Page unavailable';
      els.content.innerHTML =
        '<p class="error">Could not load <code>' + escapeHtml(def.file) + '</code>.<br>' +
        escapeHtml(err.message) + '</p>' +
        '<p>This site loads its content over <code>fetch()</code>, so it has to be served over ' +
        'HTTP rather than opened directly from the file system. From the project folder run:</p>' +
        '<p><code>python3 -m http.server 8000</code></p>' +
        '<p>then open <a href="http://localhost:8000/">http://localhost:8000/</a>.</p>';
    });
  }

  /* Turn a video URL into a player URL, or return null if it is not one. */
  function videoEmbed(href) {
    var url;
    try { url = new URL(href, location.href); } catch (e) { return null; }

    var host = url.hostname.replace(/^www\./, '');
    var id = null;

    if (host === 'youtu.be') {
      id = url.pathname.slice(1).split('/')[0];
    } else if (host === 'youtube.com' || host === 'youtube-nocookie.com') {
      id = url.searchParams.get('v') ||
           (url.pathname.match(/^\/(?:embed|shorts|v)\/([\w-]+)/) || [])[1];
    } else if (host === 'vimeo.com' || host === 'player.vimeo.com') {
      id = (url.pathname.match(/\/(?:video\/)?(\d+)/) || [])[1];
    }
    if (!id) return null;

    if (host === 'vimeo.com' || host === 'player.vimeo.com') {
      return 'https://player.vimeo.com/video/' + id;
    }

    // carry a start time through, e.g. ...?t=1328 or ?t=22m8s
    var t = url.searchParams.get('t') || url.searchParams.get('start') || '';
    var secs = /^\d+$/.test(t) ? t : (function () {
      var m = t.match(/^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/);
      if (!m || !t) return '';
      return String((+m[1] || 0) * 3600 + (+m[2] || 0) * 60 + (+m[3] || 0));
    })();

    // nocookie host so viewers are not tracked before they press play
    return 'https://www.youtube-nocookie.com/embed/' + id +
           (secs && secs !== '0' ? '?start=' + secs : '');
  }

  /* Replace a paragraph that is nothing but a video link with a player.
     A link sitting inside a sentence is left alone — only a link on its own
     line is treated as an embed. */
  function embedVideos() {
    els.content.querySelectorAll('p > a[href]').forEach(function (a) {
      var p = a.parentNode;
      if (p.children.length !== 1) return;
      if (p.textContent.trim() !== a.textContent.trim()) return;

      var src = videoEmbed(a.getAttribute('href'));
      if (!src) return;

      var wrap = document.createElement('div');
      wrap.className = 'video-embed';

      var frame = document.createElement('iframe');
      frame.src = src;
      frame.title = a.textContent.trim() || 'Embedded video';
      frame.loading = 'lazy';
      frame.allowFullscreen = true;
      frame.referrerPolicy = 'strict-origin-when-cross-origin';
      frame.setAttribute('frameborder', '0');
      frame.setAttribute('allow',
        'accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen');

      wrap.appendChild(frame);
      p.replaceWith(wrap);
    });
  }

  function decorateExternalLinks() {
    els.content.querySelectorAll('a[href^="http"]').forEach(function (a) {
      if (a.hostname !== location.hostname) {
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
      }
    });
  }

  function tagNewsEntries() {
    els.content.querySelectorAll('h2').forEach(function (h) {
      h.id = slugify(h.textContent);
    });
  }

  function scrollToTarget(slug) {
    if (!slug) { window.scrollTo(0, 0); return; }
    var target = document.getElementById(slug);
    if (!target) { window.scrollTo(0, 0); return; }
    var offset = parseInt(getComputedStyle(document.documentElement)
      .getPropertyValue('--nav-h'), 10) || 76;
    window.scrollTo({ top: target.getBoundingClientRect().top + window.pageYOffset - offset - 16 });
  }

  /* Inject the background texture as inline SVG. It cannot be a CSS
     background-image: browsers freeze animations inside an SVG used that way.
     Purely decorative, so a failure here is silent. */
  function mountBackground() {
    var host = document.querySelector('.neural-bg');
    if (!host) return;
    return fetchText(BACKGROUND_FILE).then(function (svg) {
      host.innerHTML = svg;
    }).catch(function () { /* the page is fine without it */ });
  }

  /* ---------- lightbox ---------- */

  /* Content photos open full size. Portraits in the people list are excluded:
     they are only 320px to begin with, so blowing them up gains nothing. */
  function isZoomable(img) {
    return img.tagName === 'IMG' &&
           els.content.contains(img) &&
           !img.closest('.record-list');
  }

  /* Images in the same paragraph form a gallery you can page through; a lone
     image is a group of one. */
  function groupFor(img) {
    var p = img.parentNode;
    var siblings = p ? p.querySelectorAll(':scope > img') : [];
    return siblings.length > 1 ? Array.prototype.slice.call(siblings) : [img];
  }

  var lightbox = null;

  function buildLightbox() {
    var box = document.createElement('div');
    box.className = 'lightbox';
    box.hidden = true;
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-label', 'Image viewer');
    box.innerHTML =
      '<button class="lightbox-btn lightbox-close" type="button" aria-label="Close">&#215;</button>' +
      '<button class="lightbox-btn lightbox-prev" type="button" aria-label="Previous image">&#8249;</button>' +
      '<button class="lightbox-btn lightbox-next" type="button" aria-label="Next image">&#8250;</button>' +
      '<figure class="lightbox-figure"><img alt=""><figcaption></figcaption></figure>';
    document.body.appendChild(box);

    var state = { group: [], index: 0, lastFocus: null };

    var img = box.querySelector('img');
    var cap = box.querySelector('figcaption');
    var prev = box.querySelector('.lightbox-prev');
    var next = box.querySelector('.lightbox-next');

    function show(i) {
      state.index = (i + state.group.length) % state.group.length;
      var src = state.group[state.index];
      img.src = src.currentSrc || src.src;
      var text = src.getAttribute('alt') || '';
      cap.textContent = text;
      cap.hidden = !text;
      var many = state.group.length > 1;
      prev.hidden = next.hidden = !many;
      box.setAttribute('aria-label',
        many ? 'Image ' + (state.index + 1) + ' of ' + state.group.length : 'Image viewer');
    }

    function open(target) {
      state.group = groupFor(target);
      state.lastFocus = document.activeElement;
      box.hidden = false;
      document.body.style.overflow = 'hidden';
      show(state.group.indexOf(target));
      box.querySelector('.lightbox-close').focus();
    }

    function close() {
      box.hidden = true;
      img.removeAttribute('src');
      document.body.style.overflow = '';
      if (state.lastFocus && state.lastFocus.focus) state.lastFocus.focus();
    }

    box.addEventListener('click', function (e) {
      if (e.target.closest('.lightbox-close')) return close();
      if (e.target.closest('.lightbox-prev')) return show(state.index - 1);
      if (e.target.closest('.lightbox-next')) return show(state.index + 1);
      if (!e.target.closest('.lightbox-figure')) close();   // click the backdrop
    });

    document.addEventListener('keydown', function (e) {
      if (box.hidden) return;
      if (e.key === 'Escape') { close(); }
      else if (e.key === 'ArrowLeft' && state.group.length > 1) { show(state.index - 1); }
      else if (e.key === 'ArrowRight' && state.group.length > 1) { show(state.index + 1); }
      else if (e.key === 'Tab') { e.preventDefault(); }   // keep focus in the dialog
      else { return; }
      e.stopPropagation();
    });

    return { open: open, close: close, el: box };
  }

  function setupLightbox() {
    lightbox = buildLightbox();
    els.content.addEventListener('click', function (e) {
      var img = e.target;
      if (!isZoomable(img)) return;
      // an image wrapped in a link should follow the link instead
      if (img.closest('a')) return;
      e.preventDefault();
      lightbox.open(img);
    });
  }

  /* ---------- boot ---------- */

  els.toggle.addEventListener('click', function () {
    var open = els.menu.classList.toggle('open');
    els.toggle.setAttribute('aria-expanded', String(open));
  });

  window.addEventListener('hashchange', render);

  if (!location.hash) location.replace('#/' + DEFAULT_ROUTE);
  setupLightbox();
  render();
  renderNewsSidebar();
  mountBackground();
})();
