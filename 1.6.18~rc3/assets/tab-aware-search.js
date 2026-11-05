// Activate the parent content tab(s) when the URL anchor — or a search
// highlight injected by Material's `search.highlight` feature — points at
// content hidden inside a `pymdownx.tabbed` block (`alternate_style: true`).
//
// Upstream issue: https://github.com/squidfunk/mkdocs-material/issues/4125
// (closed without a fix). Without this, search results that match content
// inside a non-default tab leave the user staring at the wrong tab.

(function () {
  function activateTabBlock(block) {
    var content = block.parentNode;
    if (!content || !content.classList || !content.classList.contains('tabbed-content')) return;

    var blocks = content.children;
    var index = -1;
    for (var i = 0; i < blocks.length; i++) {
      if (blocks[i] === block) {
        index = i;
        break;
      }
    }
    if (index === -1) return;

    var set = content.parentNode;
    if (!set) return;
    var inputs = set.querySelectorAll(':scope > input[type="radio"][name^="__tabbed_"]');
    if (!inputs || index >= inputs.length) return;

    var input = inputs[index];
    if (input.checked) return;
    input.checked = true;
    try {
      input.dispatchEvent(new Event('change', { bubbles: true }));
    } catch (e) {
      /* ignore */
    }
  }

  function activateAncestorsOf(el) {
    var node = el;
    while (node && node !== document.body) {
      if (node.classList && node.classList.contains('tabbed-block')) {
        activateTabBlock(node);
      }
      node = node.parentNode;
    }
  }

  function getHashTarget() {
    var hash = window.location.hash;
    if (!hash || hash.length < 2) return null;
    var id;
    try {
      id = decodeURIComponent(hash.slice(1));
    } catch (e) {
      id = hash.slice(1);
    }
    if (!id) return null;
    try {
      return document.getElementById(id) || document.querySelector('[id="' + CSS.escape(id) + '"]');
    } catch (e) {
      return document.getElementById(id);
    }
  }

  function runForHash() {
    try {
      var target = getHashTarget();
      if (!target) return;
      activateAncestorsOf(target);
      // Re-scroll: the browser already scrolled before tab activation, so the
      // target may now be off-screen because surrounding tab content shifted.
      target.scrollIntoView({ block: 'start' });
    } catch (e) {
      /* ignore */
    }
  }

  function runForHighlights() {
    try {
      var marks = document.querySelectorAll('mark[data-md-highlight], mark.highlight');
      if (!marks || !marks.length) return;
      var firstInTab = null;
      for (var i = 0; i < marks.length; i++) {
        var mark = marks[i];
        if (mark.closest && mark.closest('.tabbed-block')) {
          activateAncestorsOf(mark);
          if (!firstInTab) firstInTab = mark;
        }
      }
      if (firstInTab) firstInTab.scrollIntoView({ block: 'center' });
    } catch (e) {
      /* ignore */
    }
  }

  function runAll() {
    runForHash();
    // Highlights are injected after navigation; give Material a tick to mark
    // matches before we scan for them.
    setTimeout(runForHighlights, 50);
    setTimeout(runForHighlights, 250);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', runAll);
  } else {
    runAll();
  }

  window.addEventListener('hashchange', runAll);

  if (window.document$ && window.document$.subscribe) {
    window.document$.subscribe(function () {
      runAll();
    });
  }
})();
