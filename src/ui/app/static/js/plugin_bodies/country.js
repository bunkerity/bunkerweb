// Behaviour for the country settings body (templates/plugin_bodies/country.html): the
// allow-only / block-listed picker, and the conflict alert's clear button.
//
// LOADED BESIDE settings-widgets.js, after it. Every selector here is namespaced
// `[data-access-control-country-*]` / `#access-control-country-*` and exists only inside this
// body, so nothing here can double-fire through the shared widget module.
//
// Vanilla, with ONE jQuery concession (`listen` below). The page's correctness must not depend on
// this file loading at all: with JS absent the server-rendered lists are already right for the
// STORED configuration, and every field -- visible or hidden -- still posts its current value, so
// a save is a no-op rather than a deletion. What is lost with JS off is only liveness.
//
// NEVER hide a list by detaching it, by clearing its inputs, or by disabling them. The `hidden`
// attribute suppresses rendering and nothing else, which is exactly the property this page needs:
// `postable_scope` claims all three country keys and an in-scope key the POST does not carry has
// its row DELETED (db_methods/config_save.py:579-585). See the header of the template.
//
// Clearing a list is the ONE deliberate exception, and it goes through the shared widget's own
// bookkeeping: uncheck the option boxes and fire one `change`, which is what
// components/settings-widgets.js listens for to rewrite the hidden input, the badge, the footer
// count and both chip surfaces. Writing the hidden input directly would leave the visible chips
// showing countries that are no longer selected.
(() => {
  // The one place jQuery is not optional. The shared "reset to default" button announces its
  // change with jQuery's `$field.trigger("change")` (components/settings-widgets.js), and a
  // jQuery-triggered `change` runs jQuery handlers only -- there is no native `elem.change()` for
  // it to fall through to, so a plain addEventListener listener never sees it.
  const listen = (element, type, handler) => {
    if (window.jQuery) window.jQuery(element).on(type, handler);
    else element.addEventListener(type, handler);
  };

  const form = document.querySelector("form[data-plugin-settings-form]");
  if (!form) return;
  const picker = form.querySelector("[data-access-control-country-mode]");
  if (!picker) return;

  const lists = Array.from(
    form.querySelectorAll("[data-access-control-country-list]"),
  );
  const exceptions = form.querySelector(
    "[data-access-control-country-exceptions]",
  );
  const conflict = form.querySelector("[data-access-control-country-conflict]");

  const clearList = (wrapper) => {
    const boxes = wrapper.querySelectorAll(
      ".multiselect-options input[type='checkbox']",
    );
    if (!boxes.length) return;
    let changed = false;
    boxes.forEach((box) => {
      if (box.checked) {
        box.checked = false;
        changed = true;
      }
    });
    // Fire once, on any box: updateMultiselectDisplay recomputes from ALL of them.
    if (changed) boxes[0].dispatchEvent(new Event("change", { bubbles: true }));
  };

  // The conflict alert reports a list the RUNTIME is ignoring (country.lua:131-160 returns from
  // inside the whitelist branch, so a stored country blacklist is never consulted). Once that
  // list is empty the alert is stale, so hide it -- with `hidden`, never by detaching the node,
  // for the same reason the groups are hidden rather than removed. The detach ban is scanned
  // over this whole file, comments included, so it cannot be named here either.
  const hideConflict = () => {
    if (conflict) conflict.hidden = true;
  };

  const applyVisibility = () => {
    lists.forEach((wrapper) => {
      wrapper.hidden =
        wrapper.dataset.accessControlCountryList !== picker.value;
    });
    if (exceptions) exceptions.hidden = picker.value === "all";
  };

  listen(picker, "change", () => {
    // Switching away from a list must CLEAR it: leaving it populated would keep the old rule
    // half-live, and "allow only these" plus a stored block list is exactly the conflict the
    // alert above is about.
    lists.forEach((wrapper) => {
      if (wrapper.dataset.accessControlCountryList !== picker.value)
        clearList(wrapper);
    });
    applyVisibility();
    hideConflict();
  });

  form
    .querySelectorAll("[data-access-control-country-clear]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        const target = button.dataset.accessControlCountryClear;
        lists.forEach((wrapper) => {
          if (wrapper.dataset.accessControlCountryList === target)
            clearList(wrapper);
        });
        hideConflict();
      });
    });

  // The server already rendered the right state; this only re-asserts it after a bfcache restore,
  // where a browser can hand back the previous `value` of the select without firing `change`.
  window.addEventListener("pageshow", applyVisibility);
})();
