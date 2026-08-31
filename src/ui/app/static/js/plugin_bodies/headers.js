// Behaviour for the headers settings body (templates/plugin_bodies/headers.html): the one note
// that has to react to a switch rather than to a saved value.
//
// `data-headers-when="KEY=v1|v2"` is an AND of "this control is currently one of these values"
// terms, evaluated here exactly as the template evaluated it server-side. Today one element uses
// it -- the "your CSP is not being enforced" warning behind CONTENT_SECURITY_POLICY_REPORT_ONLY.
// That checkbox is the safety valve §5.5 of the candidate study complains was rendered three rows
// away from the policy it governs with nothing saying they were related; putting the consequence
// on screen the moment it is toggled is the fix, and it is worth a file for.
//
// The evaluator is a near-copy of plugin_bodies/modsecurity.js. Deliberate: a body's script is
// resolved by filename (`static/js/plugin_bodies/<plugin_id>.js`,
// app/utils.py:plugin_settings_body_script), so there is no third file a body can pull in, and
// inventing one would mean inventing a loader for it. When a THIRD body wants these ~30 lines,
// promote them into components/settings-widgets.js -- which every body already loads -- rather
// than making a fourth copy.
//
// LOADED BESIDE settings-widgets.js, after it. Every selector is namespaced `[data-headers-*]`,
// so nothing here can double-fire through the shared widget module.
//
// The page's correctness must not depend on this file loading: with JS absent the note is already
// right for the STORED value, and every field -- visible or hidden -- still posts, so a save is a
// no-op rather than a deletion. NEVER hide anything by detaching it, clearing it or disabling it:
// `postable_scope` claims every headers key, suffixed CUSTOM_HEADER / COOKIE_FLAGS rows included,
// and an in-scope key the POST does not carry has its row DELETED
// (db_methods/config_save.py:579-585).
(() => {
  // The one place jQuery is not optional: the shared "reset to default" button announces its
  // change with jQuery's `$field.trigger("change")` (components/settings-widgets.js:739-746), and
  // a jQuery-triggered `change` runs jQuery handlers only -- a plain addEventListener listener
  // never sees it, so resetting the report-only switch would leave the wrong note on screen.
  const listen = (element, type, handler) => {
    if (window.jQuery) window.jQuery(element).on(type, handler);
    else element.addEventListener(type, handler);
  };

  const form = document.querySelector("form[data-plugin-settings-form]");
  if (!form) return;

  const conditioned = Array.from(form.querySelectorAll("[data-headers-when]"));
  if (!conditioned.length) return;

  // A checkbox reports "yes"/"no" because that is what it POSTS: the shared bundle rewrites a
  // checked box's value to "yes" and inserts an explicit "no" for an unchecked one at submit time
  // (settings-widgets.js:1716-1745). Reading `.value` here would return the literal "on".
  const controlValue = (key) => {
    const control = form.querySelector(`[name='${key}']`);
    if (!control) return null;
    if (control.type === "checkbox") return control.checked ? "yes" : "no";
    return control.value;
  };

  const terms = (element) =>
    (element.dataset.headersWhen || "").trim().split(/\s+/).filter(Boolean);

  // A term naming a control that is not on the page fails closed: the element stays hidden rather
  // than appearing under a condition nothing can satisfy.
  const holds = (element) =>
    terms(element).every((term) => {
      const separator = term.indexOf("=");
      if (separator < 0) return false;
      return term
        .slice(separator + 1)
        .split("|")
        .includes(controlValue(term.slice(0, separator)));
    });

  const apply = () => {
    conditioned.forEach((element) => {
      element.hidden = !holds(element);
    });
  };

  const watched = new Set();
  conditioned.forEach((element) => {
    terms(element).forEach((term) => {
      const separator = term.indexOf("=");
      if (separator > 0) watched.add(term.slice(0, separator));
    });
  });
  watched.forEach((key) => {
    const control = form.querySelector(`[name='${key}']`);
    if (control) listen(control, "change", apply);
  });

  // The server already rendered the right state; this only re-asserts it after a bfcache restore,
  // where a browser can hand back the previous state of a control without firing `change`.
  window.addEventListener("pageshow", apply);
})();
