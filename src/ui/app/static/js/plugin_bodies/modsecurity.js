// Behaviour for the ModSecurity settings body (templates/plugin_bodies/modsecurity.html).
//
// ONE mechanism, not one branch per switch: every element that can come and go carries
// `data-modsec-when="KEY=v1|v2 KEY2=v3"` -- an AND of "this control is currently one of these
// values" terms -- and this file evaluates exactly what the template evaluated server-side. The
// banners use it too, so a warning about a state appears while the operator is putting the page
// into that state rather than after a round trip.
//
// LOADED BESIDE settings-widgets.js, after it. Every selector here is namespaced
// `[data-modsec-*]` and exists only inside this body, so nothing here can double-fire through the
// shared widget module.
//
// The page's correctness must not depend on this file loading at all: with JS absent the
// server-rendered groups are already right for the STORED state, and every field -- visible or
// hidden -- still posts its current value, so a save is a no-op rather than a deletion. What is
// lost with JS off is only liveness.
//
// NEVER hide a group by detaching it, by clearing its inputs, or by disabling them. The `hidden`
// attribute suppresses rendering and nothing else, which is exactly the property this page needs:
// `postable_scope` claims every modsecurity key and an in-scope key the POST does not carry has
// its row DELETED (db_methods/config_save.py:579-585). See the header of the template.
(() => {
  // The one place jQuery is not optional. The shared "reset to default" button announces its
  // change with jQuery's `$field.trigger("change")` (components/settings-widgets.js:739-746), and
  // a jQuery-triggered `change` runs jQuery handlers only -- there is no native `elem.change()`
  // for it to fall through to, so a plain addEventListener listener never sees it. Resetting
  // MODSECURITY_CRS_VERSION would then change the value and leave the CRS-plugins group on screen
  // under CRS 3, where it does nothing.
  const listen = (element, type, handler) => {
    if (window.jQuery) window.jQuery(element).on(type, handler);
    else element.addEventListener(type, handler);
  };

  const form = document.querySelector("form[data-plugin-settings-form]");
  if (!form) return;

  const conditioned = Array.from(form.querySelectorAll("[data-modsec-when]"));
  if (!conditioned.length) return;

  // A checkbox reports "yes"/"no" because that is what it POSTS: the shared bundle rewrites a
  // checked box's value to "yes" and inserts an explicit "no" for an unchecked one at submit time
  // (settings-widgets.js:1716-1745). Reading `.value` here instead would return the literal "on".
  const controlValue = (key) => {
    const control = form.querySelector(`[name='${key}']`);
    if (!control) return null;
    if (control.type === "checkbox") return control.checked ? "yes" : "no";
    return control.value;
  };

  // `KEY=v1|v2 KEY2=v3` -> every term must hold. A term naming a control that is not on the page
  // (USE_MODSECURITY_GLOBAL_CRS is `global`-context, so a service page never renders it) fails
  // closed: the group stays hidden rather than appearing under a condition nothing can satisfy.
  const holds = (terms) =>
    terms
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .every((term) => {
        const separator = term.indexOf("=");
        if (separator < 0) return false;
        const key = term.slice(0, separator);
        const allowed = term.slice(separator + 1).split("|");
        return allowed.includes(controlValue(key));
      });

  const apply = () => {
    conditioned.forEach((element) => {
      element.hidden = !holds(element.dataset.modsecWhen || "");
    });
  };

  // Bind to the controls the terms actually name, deduplicated -- rather than to every input on
  // the form, which would re-evaluate on every keystroke in the CRS plugin list for nothing.
  const watched = new Set();
  conditioned.forEach((element) => {
    (element.dataset.modsecWhen || "")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .forEach((term) =>
        watched.add(term.slice(0, Math.max(term.indexOf("="), 0))),
      );
  });
  watched.forEach((key) => {
    const control = key && form.querySelector(`[name='${key}']`);
    if (control) listen(control, "change", apply);
  });

  // The server already rendered the right state; this only re-asserts it after a bfcache restore,
  // where a browser can hand back the previous `value` of a select without firing `change`.
  window.addEventListener("pageshow", apply);
})();
