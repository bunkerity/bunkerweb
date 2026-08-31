mediumZoom(document.querySelectorAll('figure > img'));
mediumZoom(document.querySelectorAll('figure > p > img'));

(function () {
  var KNOWN_LANGS = ['en', 'fr', 'de', 'es', 'zh'];
  var VERSION_RE = /^(latest|next|\d[\w.\-]*)$/i;
  var currentLang = 'en';
  var searchListObserver = null;
  var bodyObserver = null;
  var observedList = null;

  function segmentPath(pathname) {
    return pathname.split('/').filter(Boolean);
  }

  function extractLangFromSegments(segments) {
    var segs = segments.slice();
    if (segs.length && VERSION_RE.test(segs[0])) segs.shift();
    for (var i = 0; i < segs.length; i++) {
      var seg = segs[i].toLowerCase();
      if (KNOWN_LANGS.indexOf(seg) !== -1) return seg;
    }
    return 'en';
  }

  function detectCurrentLang() {
    var htmlLang = (document.documentElement.getAttribute('lang') || '').toLowerCase();
    if (htmlLang) {
      htmlLang = htmlLang.split('-')[0];
      if (KNOWN_LANGS.indexOf(htmlLang) !== -1) return htmlLang;
    }
    return extractLangFromSegments(segmentPath(window.location.pathname));
  }

  function updateCurrentLang() {
    currentLang = detectCurrentLang();
  }

  function langFromLink(link) {
    if (!link) return 'en';

    var explicit = (link.getAttribute('hreflang') || '').trim().toLowerCase();
    if (explicit && KNOWN_LANGS.indexOf(explicit) !== -1) return explicit;

    var pathname = link.pathname || '';
    if (pathname) {
      var langFromPath = extractLangFromSegments(segmentPath(pathname.toLowerCase()));
      if (langFromPath) return langFromPath;
    }

    var href = link.getAttribute('href');
    if (href) {
      try {
        var url = new URL(href, window.location.href);
        var langFromHref = extractLangFromSegments(segmentPath(url.pathname.toLowerCase()));
        if (langFromHref) return langFromHref;
      } catch (e) {
        /* ignore */
      }
    }

    return 'en';
  }

  function filterSearchResults() {
    try {
      var list = document.querySelector('.md-search-result__list');
      if (!list) return;

      updateCurrentLang();

      var items = list.querySelectorAll('.md-search-result__item');

      items.forEach(function (item) {
        var link = item.querySelector('a[href]');
        if (!link) return;
        var targetLang = langFromLink(link);
        var show = targetLang === currentLang;
        item.style.display = show ? '' : 'none';
        item.hidden = !show;
      });
    } catch (e) {
      /* ignore */
    }
  }

  function ensureSearchListObserver() {
    if (!window.MutationObserver) {
      filterSearchResults();
      return;
    }
    var list = document.querySelector('.md-search-result__list');
    if (!list) return;

    if (observedList !== list) {
      observedList = list;
      if (searchListObserver) searchListObserver.disconnect();
      searchListObserver = new MutationObserver(function () {
        filterSearchResults();
      });
      searchListObserver.observe(list, { childList: true, subtree: true });
    }

    filterSearchResults();
  }

  function observeBodyForSearchList() {
    if (!window.MutationObserver || bodyObserver) return;
    var target = document.body || document.documentElement;
    bodyObserver = new MutationObserver(function (mutations) {
      for (var i = 0; i < mutations.length; i++) {
        var m = mutations[i];
        for (var j = 0; j < m.addedNodes.length; j++) {
          var node = m.addedNodes[j];
          if (node && node.nodeType === 1) {
            if (
              (node.matches && node.matches('.md-search-result__list')) ||
              (node.querySelector && node.querySelector('.md-search-result__list'))
            ) {
              ensureSearchListObserver();
              return;
            }
          }
        }
      }
    });
    bodyObserver.observe(target, { childList: true, subtree: true });
  }

  function onReady() {
    updateCurrentLang();
    ensureSearchListObserver();
    observeBodyForSearchList();

    var searchComponent = document.querySelector('[data-md-component="search"]');
    if (searchComponent) {
      searchComponent.addEventListener('click', ensureSearchListObserver, true);
    }

    var input = document.querySelector('input[data-md-component="search-query"]');
    if (input) {
      input.addEventListener('focus', ensureSearchListObserver);
      input.addEventListener('input', function () {
        setTimeout(filterSearchResults, 0);
      });
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', onReady);
  else onReady();

  if (window.document$ && window.document$.subscribe) {
    window.document$.subscribe(function () {
      updateCurrentLang();
      ensureSearchListObserver();
    });
  }
})();
