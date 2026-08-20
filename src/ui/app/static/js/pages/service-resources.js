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
  // Template -- a setting, not a resource, so it applies on Save instead of immediately.
  //
  // The picker has no `name`; it drives the ONE input[name="USE_TEMPLATE"] the page already
  // posts (models/compose_shelf.html:299-312). USE_TEMPLATE sits in the service `restore_skip`
  // (models/save_scope.py:57) and is therefore never restored, so posting it twice and not
  // posting it at all are both destructive -- the row is deleted, the service loses its
  // template, and `template_unchanged` goes False, which DROPS the outgoing template's values
  // instead of materialising the new one's (routes/services.py:878-893). Hence: resolve the
  // input lazily, and write only when there is exactly one. A greyed picker is a visible
  // no-op; a silent one is a lost template.
  // -------------------------------------------------------------------------------------
  const picker = $("#service-template-picker");
  const templateWarning = $("#service-template-warning");
  const templatePending = $("#service-template-pending");
  const templateInputs = () => $('[name="USE_TEMPLATE"]');

  const templateLabel = (value) => {
    const option = picker.find("option").filter(function () {
      return this.value === value;
    });
    return (option.length ? option.first().text().trim() : "") || value;
  };

  const disablePicker = () => {
    picker.prop("disabled", true);
    templateWarning
      .text(
        t("service.resources.template.unwired", {
          defaultValue:
            "This page does not post USE_TEMPLATE, so the template cannot be changed from here.",
        }),
      )
      .removeClass("d-none");
  };

  if (picker.length) {
    if (templateInputs().length !== 1) {
      disablePicker();
    } else {
      picker.on("change", function () {
        const target = templateInputs();
        if (target.length !== 1) {
          disablePicker();
          return;
        }
        const chosen = picker.val();
        // attr, never .data() -- .data() coerces a numeric-looking id to a Number, the same
        // defect the cloner fix chased through settings-widgets.js.
        const current = picker.attr("data-current") || "";
        target.val(chosen);

        const changed = chosen !== current;
        templatePending.toggleClass("d-none", !changed);
        if (!changed) {
          templateWarning.addClass("d-none").text("");
          return;
        }
        templateWarning
          .text(
            t("service.resources.template.switching", {
              from: templateLabel(current),
              to: templateLabel(chosen),
              defaultValue:
                "Saving switches this service from “{{from}}” to “{{to}}”. The values the current template supplied are dropped and {{to}}’s are applied — many settings move at once.",
            }),
          )
          .removeClass("d-none");
      });
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
