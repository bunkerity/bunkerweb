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

/* Settings tables: chips, copy buttons, context dots and stream badges.
   Everything is derived from the rendered markdown, so the generated
   features.md stays untouched and all five locales get the same treatment. */
(function () {
  var ID_RE = /^[A-Z][A-Z0-9_]*$/;
  var CONTEXT_RE = /^(multisite|global|全局|多站点)$/i;
  /* a translated context still has to land on the same dot color */
  var CONTEXT_ALIASES = { 全局: 'global', 多站点: 'multisite' };
  var NO_WORDS = ['no', 'non', 'nein', '否'];
  var YES_WORDS = ['yes', 'oui', 'ja', 'sí', 'si', '是'];
  var STREAM_SHORTCODES = [':white_check_mark:', ':x:', ':warning:'];
  var COPY = { en: 'Copy', fr: 'Copier', de: 'Kopieren', es: 'Copiar', zh: '复制' };
  var COPIED = { en: 'Copied', fr: 'Copié', de: 'Kopiert', es: 'Copiado', zh: '已复制' };
  var COPY_ICON =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"></rect>' +
    '<path d="M5 15V5a2 2 0 0 1 2-2h10"></path></svg>';
  var DONE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 13 4 4 10-10"></path></svg>';
  var ARROW_ICON =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14"></path><path d="m13 6 6 6-6 6"></path></svg>';

  function lang() {
    var value = (document.documentElement.getAttribute('lang') || 'en').toLowerCase().split('-')[0];
    return COPY[value] ? value : 'en';
  }

  function text(cell) {
    return (cell.textContent || '').trim();
  }

  function cellsOf(row) {
    return Array.prototype.slice.call(row.children).filter(function (cell) {
      return cell.tagName === 'TD' || cell.tagName === 'TH';
    });
  }

  /* A settings table is one whose first column holds uppercase identifiers.
     Header wording is translated per locale and differs between the plugin
     READMEs and the generator, so it is never used to decide. */
  function isSettingsTable(rows) {
    var hits = 0;
    for (var i = 0; i < rows.length; i++) {
      var first = cellsOf(rows[i])[0];
      if (!first) continue;
      var code = first.querySelector('code');
      if (code && ID_RE.test(text(code))) hits++;
    }
    return rows.length > 0 && hits >= Math.max(1, rows.length * 0.6);
  }

  function columnValues(rows, index) {
    var values = [];
    for (var i = 0; i < rows.length; i++) {
      var cell = cellsOf(rows[i])[index];
      if (!cell) continue;
      var code = cell.querySelector('code');
      values.push({
        value: text(cell),
        hasCode: !!code,
        /* the whole cell is one code span, which is what a Default column looks
           like; a prose column carries text around its inline code */
        isBareCode: !!code && text(code) === text(cell)
      });
    }
    return values;
  }

  /* Only the three columns that gain a chip or a dot are classified. Prose
     columns are left alone, so a table laid out as Setting | Description |
     Accepted values | Default cannot have its prose styled as a value. */
  function roleOf(rows, index) {
    if (index === 0) return 'setting';

    var values = columnValues(rows, index).filter(function (entry) {
      return entry.value !== '';
    });
    if (!values.length) return '';

    var allContext = values.every(function (entry) {
      return !entry.hasCode && CONTEXT_RE.test(entry.value);
    });
    if (allContext) return 'context';

    var allBoolean = values.every(function (entry) {
      var value = entry.value.toLowerCase();
      return !entry.hasCode && (NO_WORDS.indexOf(value) !== -1 || YES_WORDS.indexOf(value) !== -1);
    });
    if (allBoolean) return 'multiple';

    var bare = values.filter(function (entry) {
      return entry.isBareCode;
    });
    if (bare.length >= values.length * 0.8) return 'value';

    return '';
  }

  /* One parsed button is cloned per row rather than parsed 750 times, and one
     listener on the document serves them all. */
  var buttonTemplate = null;

  function copyButton(value) {
    if (!buttonTemplate) {
      buttonTemplate = document.createElement('button');
      buttonTemplate.type = 'button';
      buttonTemplate.className = 'bw-copy';
      buttonTemplate.innerHTML = COPY_ICON;
    }
    var button = buttonTemplate.cloneNode(true);
    button.title = COPY[lang()];
    button.setAttribute('aria-label', COPY[lang()] + ' ' + value);
    return button;
  }

  function copied(button) {
    button.classList.add('bw-copy--done');
    button.innerHTML = DONE_ICON;
    button.title = COPIED[lang()];
    setTimeout(function () {
      button.classList.remove('bw-copy--done');
      button.innerHTML = COPY_ICON;
      button.title = COPY[lang()];
    }, 1500);
  }

  function onCopyClick(event) {
    var button = event.target.closest ? event.target.closest('.bw-copy') : null;
    if (!button) return;
    var code = button.parentNode.querySelector('code');
    if (!code) return;
    var value = text(code);

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(value).then(function () {
        copied(button);
      }, function () {});
      return;
    }
    var range = document.createRange();
    range.selectNodeContents(code);
    var selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    try {
      if (document.execCommand('copy')) {
        copied(button);
        selection.removeAllRanges();
      }
    } catch (e) {
      /* no clipboard: the identifier stays selected, ready to copy by hand */
    }
  }

  function enhanceTable(table) {
    if (table.hasAttribute('data-bw-enhanced')) return;
    var body = table.querySelector('tbody');
    if (!body) return;
    var rows = Array.prototype.slice.call(body.rows);
    if (!isSettingsTable(rows)) {
      table.setAttribute('data-bw-enhanced', 'skip');
      return;
    }

    var headRow = table.tHead ? table.tHead.rows[0] : null;
    var headers = headRow ? cellsOf(headRow).map(text) : [];
    var count = headers.length || cellsOf(rows[0]).length;
    var roles = [];
    for (var i = 0; i < count; i++) roles.push(roleOf(rows, i));

    table.classList.add('bw-settings');
    table.setAttribute('data-bw-enhanced', 'yes');

    rows.forEach(function (row) {
      cellsOf(row).forEach(function (cell, index) {
        var role = roles[index] || '';
        if (role) cell.classList.add('bw-col-' + role);
        if (headers[index]) cell.setAttribute('data-bw-label', headers[index]);

        var value = text(cell);
        if (value === '') {
          cell.classList.add('bw-empty');
          return;
        }

        if (role === 'setting') {
          var code = cell.querySelector('code');
          if (code && ID_RE.test(text(code))) {
            /* the chip caps at 14rem and scrolls; the tooltip keeps the whole
               name readable without scrolling it */
            code.title = text(code);
            cell.appendChild(copyButton(text(code)));
          }
        } else if (role === 'context') {
          cell.classList.add('bw-ctx-' + (CONTEXT_ALIASES[value] || value.toLowerCase()));
        } else if (role === 'multiple' && NO_WORDS.indexOf(value.toLowerCase()) === -1) {
          var chip = document.createElement('span');
          chip.className = 'bw-multiple-yes';
          chip.textContent = value;
          cell.textContent = '';
          cell.appendChild(chip);
        }
      });
    });
  }

  /* The PRO sections open with "see the advanced usages documentation", a whole
     sentence wrapped around one link. It joins the badge row as a call to
     action, keeping the link's own localized text. */
  function advancedLink(paragraph) {
    var previous = paragraph.previousElementSibling;
    if (!previous || previous.tagName !== 'P') return null;
    var links = previous.querySelectorAll('a[href]');
    if (links.length !== 1) return null;
    var href = links[0].getAttribute('href') || '';
    if (href.indexOf('advanced') === -1 || href.indexOf('#') === -1) return null;

    var cta = document.createElement('a');
    cta.className = 'bw-badge bw-badge--cta';
    cta.href = href;
    cta.textContent = text(links[0]);
    cta.innerHTML += ARROW_ICON;
    previous.parentNode.removeChild(previous);
    return cta;
  }

  /* "STREAM support x" becomes a badge. The emoji is kept, not replaced by a
     colored dot: its alt text is the only thing that states yes, no or partial
     to a screen reader, and the shortcode in its title is locale independent. */
  function enhanceStreamLine(paragraph) {
    if (paragraph.hasAttribute('data-bw-enhanced')) return;
    var icon = paragraph.querySelector('img.twemoji, span.twemoji');
    if (!icon) return;
    if (STREAM_SHORTCODES.indexOf(icon.getAttribute('title') || '') === -1) return;
    if (paragraph.textContent.indexOf('STREAM') === -1) return;
    var label = text(paragraph.cloneNode(true));
    if (!label) return;

    var badge = document.createElement('span');
    badge.className = 'bw-badge';
    badge.appendChild(icon);
    badge.appendChild(document.createTextNode(label));
    var cta = advancedLink(paragraph);
    paragraph.textContent = '';
    paragraph.className = 'bw-badges';
    paragraph.setAttribute('data-bw-enhanced', 'yes');
    paragraph.appendChild(badge);
    if (cta) paragraph.appendChild(cta);
  }

  /* The page holds several .md-typeset roots (banner, footer, content), so the
     content ones are matched document wide rather than through the first hit. */
  function enhance() {
    Array.prototype.forEach.call(document.querySelectorAll('.md-typeset table'), enhanceTable);
    Array.prototype.forEach.call(document.querySelectorAll('.md-typeset p > img.twemoji, .md-typeset p > span.twemoji'), function (icon) {
      enhanceStreamLine(icon.parentNode);
    });
  }

  document.addEventListener('click', onCopyClick);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', enhance);
  else enhance();

  if (window.document$ && window.document$.subscribe) window.document$.subscribe(enhance);
})();

/* Content tabs that can be reached from outside.
   A tab that is not the selected one is hidden with display:none by the theme,
   which puts it out of reach of both a link to an anchor inside it and the
   browser's own find. Three ways in are added here: the URL fragment, a search
   hit marked by search.highlight, and find-in-page through hidden=until-found
   (Chrome 102+, Firefox 139+; Safari keeps the current behaviour). */
(function () {
  var UNTIL_FOUND = 'onbeforematch' in document.body;
  var resolved = false;

  function setOf(element) {
    return element.closest ? element.closest('.tabbed-set') : null;
  }

  function blocksOf(set) {
    var content = set.querySelector('.tabbed-content');
    return content ? Array.prototype.slice.call(content.children) : [];
  }

  function inputsOf(set) {
    return Array.prototype.filter.call(set.children, function (child) {
      return child.tagName === 'INPUT';
    });
  }

  /* hidden=until-found keeps the block findable; the theme's display:none does
     not, so the attribute is only worth setting where the browser honours it. */
  function sync(set) {
    if (!UNTIL_FOUND) return;
    var inputs = inputsOf(set);
    blocksOf(set).forEach(function (block, index) {
      if (inputs[index] && inputs[index].checked) block.removeAttribute('hidden');
      else block.setAttribute('hidden', 'until-found');
    });
  }

  function select(block) {
    var set = setOf(block);
    if (!set) return false;
    var index = blocksOf(set).indexOf(block);
    var input = inputsOf(set)[index];
    if (!input || input.checked) {
      sync(set);
      return false;
    }
    input.checked = true;
    sync(set);
    return true;
  }

  /* A tab can sit inside another tab, so every ancestor block is opened, the
     outermost one first. */
  function reveal(element) {
    var blocks = [];
    var node = element;
    while (node && node.closest) {
      var block = node.closest('.tabbed-block');
      if (!block) break;
      blocks.unshift(block);
      node = block.parentNode;
    }
    var opened = false;
    blocks.forEach(function (block) {
      if (select(block)) opened = true;
    });
    return opened;
  }

  function fromHash() {
    var hash = window.location.hash;
    if (hash.length < 2) return;
    var target = null;
    try {
      target = document.getElementById(decodeURIComponent(hash.slice(1)));
    } catch (e) {
      return;
    }
    if (target && reveal(target)) target.scrollIntoView();
  }

  /* search.highlight puts the matched terms in the h query parameter. They are
     read here rather than waiting for the <mark> elements the theme paints from
     them, which land after this pass has already run. */
  function searchTerms() {
    var query = window.location.search;
    if (!query) return [];
    var match = /[?&]h=([^&]*)/.exec(query);
    if (!match || !match[1]) return [];
    var raw = '';
    try {
      raw = decodeURIComponent(match[1].replace(/\+/g, ' '));
    } catch (e) {
      return [];
    }
    return raw.toLowerCase().split(/\s+/).filter(Boolean);
  }

  function fromSearchTerms() {
    var terms = searchTerms();
    if (!terms.length) return;

    var anchor = null;
    if (window.location.hash.length > 1) {
      try {
        anchor = document.getElementById(decodeURIComponent(window.location.hash.slice(1)));
      } catch (e) {
        anchor = null;
      }
    }

    var blocks = document.querySelectorAll('.md-content .tabbed-block[hidden], .md-content .tabbed-block');
    var fallback = null;
    for (var i = 0; i < blocks.length; i++) {
      var block = blocks[i];
      var haystack = (block.textContent || '').toLowerCase();
      var hit = terms.some(function (term) {
        return haystack.indexOf(term) !== -1;
      });
      if (!hit) continue;
      /* a page holds many tab sets: prefer the one the search result anchored to */
      if (anchor && anchor.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_FOLLOWING) {
        if (reveal(block)) block.scrollIntoView({ block: 'center' });
        return;
      }
      if (!fallback) fallback = block;
    }
    if (fallback && reveal(fallback)) fallback.scrollIntoView({ block: 'center' });
  }

  function enhance() {
    var sets = document.querySelectorAll('.md-content .tabbed-set');
    Array.prototype.forEach.call(sets, function (set) {
      if (set.hasAttribute('data-bw-tabs')) return;
      set.setAttribute('data-bw-tabs', 'yes');
      set.addEventListener('change', function () {
        sync(set);
      });
      if (UNTIL_FOUND) {
        blocksOf(set).forEach(function (block) {
          block.addEventListener('beforematch', function () {
            select(block);
          });
        });
      }
      sync(set);
    });
    /* DOMContentLoaded and document$ both fire on a first load; resolving the
       fragment and the search terms once keeps that scan off the second pass. */
    if (resolved) return;
    resolved = true;
    fromHash();
    fromSearchTerms();
  }

  window.addEventListener('hashchange', fromHash);

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', enhance);
  else enhance();

  if (window.document$ && window.document$.subscribe) window.document$.subscribe(enhance);
})();
