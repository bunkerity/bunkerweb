"use strict";

$(function () {
  const band = $("#service-resources-band");
  if (!band.length) return;

  const serviceId = band.data("service-id");
  const csrf = $("#csrf_token").val();

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

  const candidates = JSON.parse($("#attach-candidates").text() || "{}");

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
          text: "Nothing available to attach",
          disabled: true,
          selected: true,
        }),
      );
    }

    new bootstrap.Modal(
      document.getElementById("attach-resource-modal"),
    ).show();
  });
});
