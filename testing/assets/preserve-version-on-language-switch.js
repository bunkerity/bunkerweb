/*
  Preserve selected mike version when switching language in MkDocs Material.
  - Detect current version (via <meta name="mike-version"> or URL path)
  - Rewrite language menu links to keep that version segment
  - Works whether URL structure is /<version>/<lang>/... or /<lang>/<version>/...
*/
(function () {
  function onReady(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn, { once: true });
  }

  function getMeta(name) {
    var el = document.querySelector('meta[name="' + name + '"]');
    return el ? el.getAttribute('content') : null;
  }

  var KNOWN_LANGS = ['en', 'fr', 'de', 'es', 'zh'];
  var VERSION_RE = /^(latest|next|\d[\w.\-]*)$/i;

  // Add: Morphaius Polyglot credit configuration (update logoSrc as needed)
  var MORPHAIUS_CREDIT = {
    enabled: true,
    logoSrc: '/assets/logo-morphaius.webp',
    logoAlt: 'Morphaius',
    text: 'Translations by Morphaius Polyglot',
    href: "https://morphaius.com/"
  };

  function detectVersionFromPath(segments) {
    for (var i = 0; i < segments.length; i++) {
      if (VERSION_RE.test(segments[i])) return segments[i];
    }
    return null;
  }

  function detectOrder(segments) {
    var langIndex = -1;
    for (var i = 0; i < segments.length; i++) {
      if (KNOWN_LANGS.indexOf(segments[i]) !== -1) {
        langIndex = i;
        break;
      }
    }
    var versionIndex = -1;
    for (var j = 0; j < segments.length; j++) {
      if (VERSION_RE.test(segments[j])) {
        versionIndex = j;
        break;
      }
    }
    return { langIndex: langIndex, versionIndex: versionIndex };
  }

  function getCurrentContentPathSegments() {
    // Take current URL path and strip the leading version and language segments
    var segs = window.location.pathname.split('/').filter(Boolean);
    if (!segs.length) return [];
    // Remove leading version if present
    if (segs.length && VERSION_RE.test(segs[0])) segs.shift();
    // Remove leading language if present
    if (segs.length && KNOWN_LANGS.indexOf(segs[0]) !== -1) segs.shift();
    return segs;
  }

  function getTargetLangFromLink(a, fallbackSegments) {
    var lang = (a.getAttribute('hreflang') || '').trim().toLowerCase();
    if (KNOWN_LANGS.indexOf(lang) !== -1) return lang;
    try {
      var href = a.getAttribute('href');
      if (!href) return null;
      var url = new URL(href, window.location.origin);
      var segs = url.pathname.split('/').filter(Boolean);
      // Prefer first segment if it's a known language, else find any known lang in path
      if (segs.length && KNOWN_LANGS.indexOf(segs[0]) !== -1) return segs[0];
      for (var i = 0; i < segs.length; i++) {
        if (KNOWN_LANGS.indexOf(segs[i]) !== -1) return segs[i];
      }
    } catch (e) { /* ignore */ }
    // As a final fallback, keep the current language if we can infer it from the current path order
    if (fallbackSegments && fallbackSegments.langIndex === 0) return fallbackSegments.segs[0];
    return null;
  }

  // Insert credit item into any language menu list present in the DOM
  function ensureLangMenuCredit() {
    try {
      if (!MORPHAIUS_CREDIT || !MORPHAIUS_CREDIT.enabled) return;

      var lists = Array.prototype.slice.call(document.querySelectorAll('.md-select__list'));
      if (!lists.length) return;

      lists.forEach(function (list) {
        if (!list.querySelector('a[hreflang]')) return;
        if (list.querySelector('[data-polyglot-credit="true"]')) return;

        var li = document.createElement('li');
        li.className = 'md-select__item';
        li.setAttribute('data-polyglot-credit', 'true');
        // Subtle visual separator and spacing for readability
        li.style.borderTop = '1px solid var(--md-default-fg-color--lightest, rgba(0,0,0,0.08))';
        li.style.marginTop = '0.25rem';
        li.style.paddingTop = '0.25rem';

        var node;
        if (MORPHAIUS_CREDIT.href) {
          node = document.createElement('a');
          node.href = MORPHAIUS_CREDIT.href;
          node.target = '_blank';
          node.rel = 'noopener noreferrer';
          node.className = 'md-select__link';
        } else {
          node = document.createElement('div');
          node.className = 'md-select__link';
          node.setAttribute('role', 'note');
          node.setAttribute('aria-disabled', 'true');
          node.style.cursor = 'default';
        }

        // Layout for better readability
        node.style.display = 'flex';
        node.style.alignItems = 'center';
        node.style.gap = '0.5em';
        node.style.whiteSpace = 'nowrap';
        node.style.lineHeight = '1.3';
        node.style.fontSize = '0.95em';
        node.setAttribute('aria-label', MORPHAIUS_CREDIT.text || 'Translations by Morphaius Polyglot');
        node.title = MORPHAIUS_CREDIT.text || 'Translations by Morphaius Polyglot';

        if (MORPHAIUS_CREDIT.logoSrc) {
          var img = document.createElement('img');
          img.src = MORPHAIUS_CREDIT.logoSrc;
          img.alt = MORPHAIUS_CREDIT.logoAlt || 'Morphaius';
          // Keep aspect ratio for a 4797x1436 logo; scale via height only
          img.style.height = '1.25em';
          img.style.width = 'auto';
          img.style.maxWidth = '8em';
          img.style.flexShrink = '0';
          img.style.verticalAlign = 'middle';
          img.style.marginRight = '0.25em';
          img.style.objectFit = 'contain';
          img.decoding = 'async';
          img.loading = 'lazy';
          node.appendChild(img);
        }

        var span = document.createElement('span');
        span.textContent = MORPHAIUS_CREDIT.text || 'Translations by Morphaius Polyglot';
        node.appendChild(span);

        li.appendChild(node);
        list.appendChild(li);
      });
    } catch (e) { /* ignore */ }
  }

  function rewriteLanguageLinks() {
    try {
      var pathSegments = window.location.pathname.split('/').filter(Boolean);
      var currentVersion = (getMeta('mike-version') || '').trim();
      if (!currentVersion) currentVersion = detectVersionFromPath(pathSegments);
      if (!currentVersion) return; // Not a versioned page
      var order = detectOrder(pathSegments);
      var contentSegs = getCurrentContentPathSegments();
      var trailingSlashFromCurrent = /\/$/.test(window.location.pathname);

      var anchors = Array.prototype.slice.call(
        document.querySelectorAll(
          '[data-md-component="language"] a[href], a[hreflang][href]'
        )
      );
      if (!anchors.length) return;

      anchors.forEach(function (a) {
        try {
          var href = a.getAttribute('href');
          if (!href) return;
          var url = new URL(href, window.location.origin);
          var targetLang = getTargetLangFromLink(a, { segs: pathSegments, langIndex: order.langIndex });
          if (!targetLang || KNOWN_LANGS.indexOf(targetLang) === -1) return;

          // Enforce structure: /<version>/<lang>/<current_page>
          var newSegs = [currentVersion, targetLang].concat(contentSegs);

          // Preserve link's original hash and query, but use current page trailing slash style
          var hadHash = url.hash && url.hash !== '#';
          if (!hadHash && window.location.hash) url.hash = window.location.hash;
          url.pathname = '/' + newSegs.join('/') + (trailingSlashFromCurrent ? '/' : '');
          a.setAttribute('href', url.toString());
        } catch (e) {
          // ignore per-link errors
        }
      });
    } catch (e) {
      // silent fail
    }
  }

  onReady(function () {
    rewriteLanguageLinks();
    ensureLangMenuCredit();

    // Re-apply on any click to cover dynamic menu rendering
    document.addEventListener('click', function () {
      setTimeout(function () {
        rewriteLanguageLinks();
        ensureLangMenuCredit();
      }, 0);
    });

    // Observe the whole document for injected select lists (safe, lightweight callback)
    var target = document.body || document.documentElement;
    if (target && window.MutationObserver) {
      var mo = new MutationObserver(function (mutations) {
        var needsRun = false;
        for (var i = 0; i < mutations.length && !needsRun; i++) {
          var m = mutations[i];
          for (var j = 0; j < m.addedNodes.length && !needsRun; j++) {
            var n = m.addedNodes[j];
            if (n && n.nodeType === 1) {
              if (n.matches && n.matches('.md-select__list')) needsRun = true;
              else if (n.querySelector && n.querySelector('.md-select__list')) needsRun = true;
            }
          }
        }
        if (needsRun) {
          rewriteLanguageLinks();
          ensureLangMenuCredit();
        }
      });
      mo.observe(target, { childList: true, subtree: true });
    }
  });
})();
