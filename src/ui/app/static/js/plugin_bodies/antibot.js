// Behaviour for the antibot settings body (templates/plugin_bodies/antibot.html): the mode
// picker, the reCAPTCHA classic/Enterprise sub-toggle, and the country-filter picker.
//
// LOADED BESIDE settings-widgets.js, after it. Every selector here is namespaced
// `[data-antibot-*]` / `#antibot-*` and exists only inside this body, so nothing here can
// double-fire through the shared widget module.
//
// Vanilla, with ONE jQuery concession (`listen` below). The page's correctness must not depend
// on this file loading at all: with JS absent the server-rendered groups are already right for
// the STORED mode, and every field -- visible or hidden -- still posts its current value, so a
// save is a no-op rather than a deletion. What is lost with JS off is only
// liveness: the picker stops re-arranging the page.
//
// NEVER hide a group by detaching it, by clearing its inputs, or by disabling them. The `hidden`
// attribute suppresses rendering and nothing else, which is exactly the property this page needs:
// `postable_scope` claims all 33 antibot keys and an in-scope key the POST does not carry has its
// row DELETED (db_methods/config_save.py:579-585). See the header of the template.
(() => {
  // The one place jQuery is not optional. The shared "reset to default" button announces its
  // change with jQuery's `$field.trigger("change")` (components/settings-widgets.js:739-746), and
  // a jQuery-triggered `change` runs jQuery handlers only -- there is no native `elem.change()`
  // for it to fall through to, so a plain addEventListener listener never sees it. Resetting the
  // mode picker would then change the value and leave the page showing the OLD provider's fields.
  // Binding through jQuery when it is present covers both: jQuery's own delegation is installed
  // with a native listener, so real user input still arrives.
  const listen = (element, type, handler) => {
    if (window.jQuery) window.jQuery(element).on(type, handler);
    else element.addEventListener(type, handler);
  };

  const form = document.querySelector("form[data-plugin-settings-form]");
  if (!form) return;
  const modeSelect = form.querySelector("select[name='USE_ANTIBOT']");
  if (!modeSelect) return;

  const classicBox = form.querySelector(
    "input[name='ANTIBOT_RECAPTCHA_CLASSIC']",
  );
  const groups = Array.from(form.querySelectorAll("[data-antibot-group]"));

  // A group with no `data-antibot-modes` is always on screen. `data-antibot-classic` is an
  // ADDITIONAL condition, never a replacement -- the two reCAPTCHA credential blocks are both
  // `modes="recaptcha"` and differ only in that attribute (antibot.lua:769-819).
  const applyVisibility = () => {
    const mode = modeSelect.value;
    const classic = classicBox ? (classicBox.checked ? "yes" : "no") : "yes";
    groups.forEach((group) => {
      const modes = group.dataset.antibotModes;
      const wants = group.dataset.antibotClassic;
      const modeOk = !modes || modes.split(" ").includes(mode);
      const classicOk = !wants || wants === classic;
      group.hidden = !(modeOk && classicOk);
    });
  };

  listen(modeSelect, "change", applyVisibility);
  if (classicBox) listen(classicBox, "change", applyVisibility);

  // ------------------------------------------------------------------- country picker
  // ANTIBOT_IGNORE_COUNTRY and ANTIBOT_ONLY_COUNTRY are ORed by the runtime
  // (antibot.lua:1198-1203): an ignore-list hit, OR being outside the only-list, exempts the
  // request. The picker presents that as one choice, so switching away from a list must CLEAR
  // it -- leaving it populated would silently keep half the old rule live.
  //
  // Clearing goes through the shared widget's own bookkeeping: uncheck the option boxes and fire
  // one `change`, which is what components/settings-widgets.js listens for to rewrite the hidden
  // input, the badge, the footer count and both chip surfaces. Writing the hidden input directly
  // would leave the visible chips showing countries that are no longer selected.
  const picker = form.querySelector("[data-antibot-country-mode]");
  const lists = Array.from(
    form.querySelectorAll("[data-antibot-country-list]"),
  );

  const clearCountryList = (wrapper) => {
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

  if (picker && lists.length) {
    listen(picker, "change", () => {
      lists.forEach((wrapper) => {
        const on = wrapper.dataset.antibotCountryList === picker.value;
        wrapper.hidden = !on;
        if (!on) clearCountryList(wrapper);
      });
    });
  }

  // The server already rendered the right state; this only re-asserts it after a bfcache
  // restore, where a browser can hand back the previous `value` of the select without firing
  // `change`.
  window.addEventListener("pageshow", applyVisibility);
})();
