"use strict";

$(function () {
  const band = $("#service-resources-band");
  if (!band.length) return;

  const serviceId = band.data("service-id");
  const csrf = $("#csrf_token").val();

  // i18next is loaded by base.html but is not guaranteed to be (components/copy-button.js
  // guards the same way), so every message carries its own English defaultValue and the
  // fallback path interpolates it the way i18next would.
  const interpolate = (text, options) =>
    String(text).replace(/{{(\w+)}}/g, (_, key) =>
      options[key] === undefined ? "" : options[key],
    );
  const t = (key, options) =>
    typeof i18next !== "undefined"
      ? i18next.t(key, options)
      : interpolate(options.defaultValue || "", options);

  band.on("click", ".detach-resource", function () {
    const button = $(this);
    const family = button.data("family");
    if (!window.confirm(`Detach this ${family} from ${serviceId}?`)) return;

    $("<form>", {
      method: "POST",
      action: `${window.location.pathname}/resources/detach`,
    })
      .append($("<input>", { type: "hidden", name: "csrf_token", value: csrf }))
      .append($("<input>", { type: "hidden", name: "family", value: family }))
      .append(
        $("<input>", {
          type: "hidden",
          name: "resource_id",
          value: button.data("resource-id"),
        }),
      )
      .append(
        $("<input>", {
          type: "hidden",
          name: "match_path",
          value: button.closest(".resource-chip").data("match-path") || "",
        }),
      )
      .appendTo("body")
      .trigger("submit");
  });

  // -------------------------------------------------------------------------------------
  // Template LAYERS -- a setting, not a resource, so it applies on Save instead of immediately.
  //
  // USE_TEMPLATE is an ORDERED LIST (multivalue, separator " "): layers apply left to right and
  // a later one overrides an earlier one. Nothing in this block has a `name`; it drives the ONE
  // input[name="USE_TEMPLATE"] the page already posts (models/compose_shelf.html). USE_TEMPLATE
  // sits in the service `restore_skip` (models/save_scope.py) and is therefore never restored,
  // so posting it twice and not posting it at all are both destructive. Hence: resolve the input
  // lazily, and write only when there is exactly one. A disabled control is a visible no-op; a
  // silent one is a lost layer.
  //
  // NO INTERACTION MAY SILENTLY DROP A LAYER. Three things enforce that:
  //   1. the chips are rendered SERVER-SIDE in stored order, so with this file broken the list
  //      is still correct on screen and the hidden input still carries the stored value;
  //   2. the only removal gesture is an explicit click on a chip's x;
  //   3. every write goes through renderLayers(), which rebuilds the hidden input from the
  //      SAME array the chips are rendered from -- the two can never disagree.
  // -------------------------------------------------------------------------------------
  const layersRoot = $("#service-template-layers");
  const layerList = $("#service-template-layer-list");
  const layerEmpty = $("#service-template-empty");
  const picker = $("#service-template-picker");
  const addButton = $("#service-template-add");
  const templateWarning = $("#service-template-warning");
  const templatePending = $("#service-template-pending");
  const templateInputs = () => $('[name="USE_TEMPLATE"]');

  // Same contract as common_utils.split_templates: split on the literal separator, drop
  // empties. NOT /\s+/ -- the storage contract (normalize_list_value) only ever treats " " as
  // a separator, so a tab is part of a (bogus) template id, not a break between two.
  const splitTemplates = (value) =>
    String(value || "")
      .split(" ")
      .map((item) => item.trim())
      .filter(Boolean);

  // .filter() and not an interpolated attribute selector: a template id is user-created, so
  // building a selector from it would need CSS.escape (and the scanner in
  // tests/unit/ui/test_untranslated_js_literals.py walks the file lexically -- a template
  // literal carrying nested quotes desynchronises it and silently hides every later literal).
  const templateLabel = (id) => {
    const stored = layerList
      .children("li")
      .filter(function () {
        return $(this).attr("data-id") === id;
      })
      .find(".text-truncate")
      .first();
    if (stored.length) return stored.text().trim() || id;
    const option = picker.find("option").filter(function () {
      return this.value === id;
    });
    return (option.length ? option.first().text().trim() : "") || id;
  };

  const disableLayerControls = (message) => {
    picker.prop("disabled", true);
    addButton.prop("disabled", true);
    layerList.find("button").prop("disabled", true);
    templateWarning.text(message).removeClass("d-none");
  };

  if (layersRoot.length) {
    // How many settings each PAIR of templates shares (routes/services.py:template_overlaps).
    // Symmetric, so it answers every order the user can build here.
    let overlaps = {};
    try {
      overlaps = JSON.parse(layersRoot.attr("data-overlaps") || "{}");
    } catch (e) {
      overlaps = {};
    }

    const stored = splitTemplates(layersRoot.attr("data-current"));
    // Seeded from the SERVER-RENDERED chips, not from the stored string, so the array and the
    // DOM start out identical by construction.
    let layers = layerList
      .children("li")
      .map(function () {
        return $(this).attr("data-id");
      })
      .get();

    const sharedWith = (id, otherId) => {
      // hasOwnProperty, not a bare lookup: template ids are user-created, and one named
      // "constructor" would otherwise resolve off Object.prototype.
      if (!Object.prototype.hasOwnProperty.call(overlaps, id)) return 0;
      const row = overlaps[id];
      return Object.prototype.hasOwnProperty.call(row, otherId)
        ? row[otherId]
        : 0;
    };

    // Which LATER layers override some of this one's settings. Names, not a summed count:
    // two later layers can override the same key, so adding the pairwise counts would
    // over-report. The pair counts go in the title attribute, where each one is honest.
    const overriddenBy = (index) =>
      layers
        .slice(index + 1)
        .filter((later) => sharedWith(layers[index], later) > 0)
        .map((later) => ({
          id: later,
          shared: sharedWith(layers[index], later),
        }));

    function renderLayers() {
      layerList.empty();
      layers.forEach((id, index) => {
        const shadowing = overriddenBy(index);
        const row = $("<li>", {
          class:
            "resource-chip d-flex justify-content-between align-items-center border rounded px-2 py-1 mb-1",
          "data-id": id,
        });
        row.append(
          $("<span>", { class: "text-truncate", text: templateLabel(id) }),
        );

        const controls = $("<span>", {
          class: "d-flex align-items-center gap-1 ms-2",
        });
        if (shadowing.length) {
          controls.append(
            $("<span>", {
              class: "badge bg-warning text-dark layer-overridden",
              text: t("service.resources.template.overridden_badge", {
                defaultValue: "overridden",
              }),
              // Two things about the string below, both load-bearing:
              //  * the typographic apostrophe, not a straight one -- and NO apostrophe may
              //    appear in a comment INSIDE a t(...) call either: _translation_ranges in
              //    tests/unit/ui/test_untranslated_js_literals.py scans for the closing paren
              //    WITHOUT stripping comments, so one stray quote there swallows every later
              //    literal in the file into this call range. That is why these lines sit here,
              //    outside the call, rather than next to the property they describe.
              //  * escapeValue false, because jQuery .text()/attr already escape; leaving t()
              //    to escape as well would render a template named A&B as A&amp;B.
              title: shadowing
                .map((entry) =>
                  t("service.resources.template.overridden_by", {
                    count: entry.shared,
                    name: templateLabel(entry.id),
                    defaultValue:
                      "{{name}} overrides {{count}} of this template\u2019s settings.",
                    interpolation: { escapeValue: false },
                  }),
                )
                .join(" "),
            }),
          );
        }
        controls.append(
          $("<span>", {
            class: "badge bg-secondary layer-position",
            text: index + 1,
          }),
        );
        controls.append(
          $("<button>", {
            type: "button",
            class: "btn btn-sm btn-link p-0 layer-up",
            "aria-label": t("service.resources.template.move_up", {
              defaultValue: "Move this template earlier",
            }),
            disabled: index === 0,
          }).append(
            $("<i>", { class: "bx bx-up-arrow-alt", "aria-hidden": "true" }),
          ),
        );
        controls.append(
          $("<button>", {
            type: "button",
            class: "btn btn-sm btn-link p-0 layer-down",
            "aria-label": t("service.resources.template.move_down", {
              defaultValue: "Move this template later",
            }),
            disabled: index === layers.length - 1,
          }).append(
            $("<i>", { class: "bx bx-down-arrow-alt", "aria-hidden": "true" }),
          ),
        );
        controls.append(
          $("<button>", {
            type: "button",
            class: "btn btn-sm btn-link p-0 text-danger layer-remove",
            "aria-label": t("service.resources.template.remove", {
              defaultValue: "Remove this template",
            }),
          }).append($("<i>", { class: "bx bx-x", "aria-hidden": "true" })),
        );

        row.append(controls);
        layerList.append(row);
      });

      layerEmpty.toggleClass("d-none", layers.length > 0);
      // A template already attached is not an add candidate; keep it selectable nowhere rather
      // than letting a duplicate in (harmless to the merge, confusing on screen).
      picker.find("option").each(function () {
        $(this).prop("disabled", layers.indexOf(this.value) !== -1);
      });
      const firstFree = picker.find("option:not(:disabled)").first();
      addButton.prop("disabled", firstFree.length === 0);
      if (picker.find("option:selected").prop("disabled") && firstFree.length) {
        picker.val(firstFree.val());
      }

      commit();
    }

    // The ONLY writer of the hidden input, and it always writes the whole list.
    function commit() {
      const target = templateInputs();
      if (target.length !== 1) {
        // The page does not post USE_TEMPLATE (or posts it twice): editing here would be a
        // silent no-op at best and a lost layer at worst. Freeze the controls and say so.
        disableLayerControls(
          t("service.resources.template.unwired", {
            defaultValue:
              "This page does not post USE_TEMPLATE, so the template cannot be changed from here.",
          }),
        );
        return;
      }

      const value = layers.join(" ");
      target.val(value);

      const changed = value !== stored.join(" ");
      templatePending.toggleClass("d-none", !changed);
      if (!changed) {
        templateWarning.addClass("d-none").text("");
        return;
      }

      const removed = stored.filter((id) => layers.indexOf(id) === -1);
      const added = layers.filter((id) => stored.indexOf(id) === -1);
      const messages = [];
      if (removed.length) {
        messages.push(
          t("service.resources.template.removing", {
            names: removed.map(templateLabel).join(", "),
            defaultValue:
              "Saving detaches {{names}}. The values those templates supplied are dropped.",
            interpolation: { escapeValue: false },
          }),
        );
      }
      if (added.length) {
        messages.push(
          t("service.resources.template.adding", {
            names: added.map(templateLabel).join(", "),
            defaultValue:
              "Saving applies {{names}}. Many settings can move at once.",
            interpolation: { escapeValue: false },
          }),
        );
      }
      if (!messages.length) {
        messages.push(
          t("service.resources.template.reordered", {
            defaultValue:
              "Saving changes the template order. Later templates override earlier ones, so the effective values change.",
          }),
        );
      }
      templateWarning.text(messages.join(" ")).removeClass("d-none");
    }

    if (templateInputs().length !== 1) {
      disableLayerControls(
        t("service.resources.template.unwired", {
          defaultValue:
            "This page does not post USE_TEMPLATE, so the template cannot be changed from here.",
        }),
      );
    } else {
      addButton.on("click", function () {
        const chosen = picker.val();
        if (!chosen || layers.indexOf(chosen) !== -1) return;
        layers.push(chosen);
        renderLayers();
      });

      // Delegated: renderLayers() replaces every row, so per-row handlers would go stale.
      //
      // Both handlers key on the row's POSITION, never on its template id. Repeats are legal --
      // "low low high" is a valid stored value (spec: last-wins is idempotent under repetition,
      // so nothing rejects it from env vars, autoconf labels, the API or the raw pane) and
      // renderLayers() draws one row per layer including repeats. Keyed on the id instead,
      // `filter(layer !== id)` deleted EVERY copy on one click and `indexOf(id)` moved the FIRST
      // chip when you clicked the second -- both silent drops of a layer, which is exactly what
      // the header invariant above forbids. `.index()` is the row's position among its siblings,
      // and renderLayers() builds the rows from `layers` in order, so the two cannot disagree.
      layerList.on("click", ".layer-remove", function () {
        const index = $(this).closest("li").index();
        if (index < 0 || index >= layers.length) return;
        layers.splice(index, 1);
        renderLayers();
      });

      layerList.on("click", ".layer-up, .layer-down", function () {
        const index = $(this).closest("li").index();
        const target = $(this).hasClass("layer-up") ? index - 1 : index + 1;
        if (
          index < 0 ||
          index >= layers.length ||
          target < 0 ||
          target >= layers.length
        )
          return;
        const moved = layers[index];
        layers[index] = layers[target];
        layers[target] = moved;
        renderLayers();
      });

      renderLayers();
    }
  }

  // -------------------------------------------------------------------------------------
  // Attach dialog, with the server-side conflict rules surfaced before the round trip.
  // -------------------------------------------------------------------------------------
  const candidates = JSON.parse($("#attach-candidates").text() || "{}");
  const conflicts = JSON.parse($("#attach-conflicts").text() || "{}");
  const claimedPaths = conflicts.paths || {};

  const candidateRow = (family, id) =>
    (candidates[family] || []).find((row) => String(row.id) === String(id));

  // db_methods/locations.py:96-108, both of its loops and in its order: an attached resource
  // first, then the service's own inline settings. The incoming resource's own claims are
  // skipped exactly as location_conflict skips them (:96 passes it as exclude_resource_id),
  // so re-attaching a pool onto the path it already holds is not reported as a conflict.
  function pathConflict(path, resourceId) {
    // hasOwnProperty, not a bare lookup: match_path is typed by hand, and "constructor" or
    // "toString" would otherwise resolve off Object.prototype and block a legal attach.
    const claim = Object.prototype.hasOwnProperty.call(claimedPaths, path)
      ? claimedPaths[path]
      : null;
    if (!claim) return "";
    if (claim.resource_id && claim.resource_id === String(resourceId))
      return "";
    if (claim.kind === "inline") {
      return t("service.resources.conflict.inline", {
        service: serviceId,
        path: path,
        family: claim.name,
        defaultValue:
          "{{service}} already serves {{path}} through its own {{family}} settings. Clear those settings for {{path}}, or use a different path.",
      });
    }
    return t("service.resources.conflict.resource", {
      service: serviceId,
      path: path,
      kind: claim.kind,
      name: claim.name,
      defaultValue:
        "{{service}} already serves {{path}} through the {{kind}} “{{name}}”. Detach “{{name}}”, or give one of them a different path.",
    });
  }

  function evaluateConflicts() {
    const family = $("#attach-family").val();
    const row = candidateRow(family, $("#attach-resource-id").val());
    let blocking = "";
    let warning = "";

    if (row && family === "upstream") {
      // A stream pool has no path at all (db_methods/upstreams.py:120-133), so the path box
      // would be a lie; what it can collide with is the one stream pool a service may carry.
      const isStream = row.protocol === "stream";
      $("#attach-match-path-row").toggleClass("d-none", isStream);
      if (isStream) {
        const held = conflicts.stream_upstream;
        if (held && String(held.id) !== String(row.id)) {
          blocking = t("service.resources.conflict.stream", {
            service: serviceId,
            name: held.name,
            defaultValue:
              "A stream service proxies every connection to a single backend, and {{service}} already uses the upstream “{{name}}”. Detach it first.",
          });
        } else if (
          // db_methods/upstreams.py:134-141 -- the pool would TAKE THE PLACE of an inline
          // REVERSE_PROXY_HOST on a stream service, so the attach is refused rather than
          // silently overriding it. Reverse proxy only: that branch consults
          // LOCATION_SETTINGS["reverse proxy"], not gRPC and not redirect.
          Object.values(claimedPaths).some(
            (claim) =>
              claim.kind === "inline" && claim.name === "reverse proxy",
          )
        ) {
          blocking = t("service.resources.conflict.stream_inline", {
            service: serviceId,
            defaultValue:
              "{{service}} already has its own backend in REVERSE_PROXY_HOST. Clear that setting to let the upstream take over.",
          });
        }
      } else {
        blocking = pathConflict($("#attach-match-path").val() || "/", row.id);
      }
    } else if (row && family === "redirect") {
      blocking = pathConflict(row.from_path, row.id);
    } else if (row && family === "certificate") {
      const primary = conflicts.primary_certificate;
      if (
        $("#attach-primary").is(":checked") &&
        primary &&
        String(primary.id) !== String(row.id)
      ) {
        warning = t("service.resources.conflict.primary", {
          name: primary.name,
          defaultValue:
            "“{{name}}” is currently the primary certificate for this service and will be demoted without further warning. The primary is the one actually deployed.",
        });
      }
    }

    $("#attach-conflict").text(blocking).toggleClass("d-none", !blocking);
    $("#attach-primary-warning").text(warning).toggleClass("d-none", !warning);
    // A blocking message is a refusal the API would issue anyway. The primary demotion is not
    // a refusal -- it succeeds and silently changes which certificate is served -- so it warns
    // and never disables Attach.
    $("#attach-submit").prop("disabled", Boolean(blocking));
  }

  $("#attach-resource-modal").on(
    "change input",
    "#attach-resource-id, #attach-match-path, #attach-primary",
    evaluateConflicts,
  );

  band.on("click", ".attach-resource", function () {
    const family = $(this).data("family");
    const rows = candidates[family] || [];

    $("#attach-family").val(family);
    // Reset state left over from a previous open -- d-none only hides the row, it
    // doesn't clear the input, so a stale path/checkbox would otherwise ride along
    // into an unrelated family's submission.
    $("#attach-match-path").val("/");
    $("#attach-primary").prop("checked", false);
    $("#attach-match-path-row").toggleClass("d-none", family !== "upstream");
    $("#attach-primary-row").toggleClass("d-none", family !== "certificate");

    const select = $("#attach-resource-id").empty();
    rows.forEach((row) => {
      select.append(
        $("<option>", {
          value: row.id,
          text: row.name || row.common_name || row.to_url || row.id,
        }),
      );
    });
    if (!rows.length) {
      select.append(
        $("<option>", {
          value: "",
          text: t(
            "service.resources.nothing_available",
            "Nothing available to attach.",
          ),
          disabled: true,
          selected: true,
        }),
      );
    }

    evaluateConflicts();

    new bootstrap.Modal(
      document.getElementById("attach-resource-modal"),
    ).show();
  });
});
