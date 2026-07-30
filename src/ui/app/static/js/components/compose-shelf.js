// Behaviour for the compose shelf (templates/models/compose_shelf.html): the multi-key
// switch, the On/All/Changed filter and the "Show N more" fold.
//
// SAFE TO LOAD BESIDE EITHER settings-widgets.js OR plugins-settings.js. Every selector
// here is namespaced `[data-shelf-*]` / `.shelf-*` and exists only inside the shelf, so
// none of the 17 delegated selectors those two files duplicate can double-fire through
// this one. (Those two still must never load together -- see settings-widgets.js's header.)
//
// Vanilla on purpose: it needs no jQuery, no bootstrap and no i18next, so it cannot be
// killed by a throw in another module's init. The shelf's correctness must not depend on
// this file loading at all -- with JS absent every row still posts its keys at their
// current stored value, which is a no-op save rather than a deletion.
(() => {
  const shelf = document.getElementById("compose-shelf");
  if (!shelf) return;

  const rows = Array.from(shelf.querySelectorAll("[data-shelf-row]"));

  // ---------------------------------------------------------------- multi-key switch
  // `limit` declares USE_LIMIT_REQ + USE_LIMIT_CONN and renders ONE switch: the first key
  // is the checkbox, the siblings are hidden inputs. OFF must write EVERY declared key to
  // its inactive value, or "off" leaves USE_LIMIT_CONN at "yes" and the connection limiter
  // keeps running. ON restores what was stored rather than forcing an active value, so a
  // toggle off-then-on is an exact undo.
  shelf.addEventListener("change", (event) => {
    const box = event.target;
    if (!box.classList || !box.classList.contains("shelf-switch")) return;
    const row = box.closest("[data-shelf-row]");
    if (!row) return;
    row.querySelectorAll("[data-shelf-sibling]").forEach((sibling) => {
      if (sibling.dataset.shelfCurrent === undefined) {
        sibling.dataset.shelfCurrent = sibling.value;
      }
      sibling.value = box.checked
        ? sibling.dataset.shelfCurrent
        : sibling.dataset.shelfInactive;
    });
  });

  // ---------------------------------------------------------------- filter + fold
  // Rows are hidden with `display:none` and NOTHING ELSE. Detaching or rebuilding a row
  // would stop its hidden inputs posting while its keys stay in scope, and
  // `Database.save_config` deletes any in-scope key the form did not post.
  let filter = "all";
  let expanded = false;

  const matchesFilter = (row) => {
    if (filter === "on") return row.dataset.shelfOn === "true";
    if (filter === "changed") return row.dataset.shelfChanged === "true";
    return true;
  };

  const apply = () => {
    rows.forEach((row) => {
      const folded = row.hasAttribute("data-shelf-folded") && !expanded;
      row.style.display = !folded && matchesFilter(row) ? "" : "none";
    });
  };

  shelf.querySelectorAll("[data-shelf-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      filter = button.dataset.shelfFilter;
      shelf
        .querySelectorAll("[data-shelf-filter]")
        .forEach((other) => other.classList.toggle("active", other === button));
      // "On" and "Changed" are explicit requests to see a subset, so they unfold: a folded
      // row that matches the filter would otherwise stay invisible with no way to reach it.
      if (filter !== "all") expanded = true;
      apply();
    });
  });

  const showMore = document.getElementById("compose-shelf-show-more");
  if (showMore) {
    showMore.addEventListener("click", () => {
      expanded = true;
      showMore.style.display = "none";
      apply();
    });
  }

  apply();
})();
