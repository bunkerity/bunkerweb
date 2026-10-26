/* Ranked "top N" table with a share bar, plus a Detail modal holding the full list.
 *
 * Shared by /bans (bans by reason) and /certificates (top issuers). Labels are untrusted free
 * text, so every cell is built with jQuery `.text()`, never through an HTML string.
 *
 *   BWTopTable.render($container, { items, head, caption, detailLabel, onDetail })
 *   BWTopTable.openDetail({ title, head, caption, items, meta, closeLabel })
 *
 * `items` is [{ label, pct, count? }]; pct is a 0-100 number.
 */
window.BWTopTable = (function () {
  function table({ items, head, caption }) {
    const $table = $("<table>").addClass("table table-sm align-middle mb-0");
    $table.append($("<caption>").addClass("visually-hidden").text(caption));
    $table.append(
      $("<thead>").append(
        $("<tr>").append(
          $("<th>").attr("scope", "col").css("width", "2.75rem").text("#"),
          $("<th>").attr("scope", "col").text(head.label),
          $("<th>")
            .attr({ scope: "col", style: "width: 42%" })
            .text(head.share),
        ),
      ),
    );
    const $body = $("<tbody>");
    items.forEach((item, index) => {
      const pct = Number.isFinite(item.pct) ? item.pct : 0;
      $body.append(
        $("<tr>").append(
          $("<td>")
            .addClass("text-muted")
            .text(index + 1),
          $("<td>").append($("<span>").addClass("fw-medium").text(item.label)),
          $("<td>").append(
            $("<div>")
              .addClass("d-flex align-items-center gap-2")
              .append(
                $("<div>")
                  .addClass("progress flex-grow-1")
                  .css("height", "6px")
                  .append(
                    $("<div>")
                      .addClass("progress-bar")
                      .css("width", `${pct}%`)
                      .attr({
                        role: "progressbar",
                        "aria-valuenow": pct,
                        "aria-valuemin": 0,
                        "aria-valuemax": 100,
                      }),
                  ),
                $("<span>")
                  .addClass("font-monospace small text-muted text-nowrap")
                  .text(`${pct}%`),
              ),
          ),
        ),
      );
    });
    return $table.append($body);
  }

  function render($container, options) {
    $container.empty().append(table(options));
    if (options.onDetail) {
      $container.append(
        $("<div>")
          .addClass("d-flex justify-content-end mt-3")
          .append(
            $("<button>")
              .attr("type", "button")
              .addClass("btn btn-sm btn-outline-secondary")
              .text(options.detailLabel)
              .on("click", options.onDetail),
          ),
      );
    }
  }

  function openDetail(options) {
    const id = "bw-top-detail-modal";
    $(`#${id}`).remove();
    const titleId = `${id}-title`;
    const $footer = $("<div>").addClass("modal-footer");
    if (options.meta) {
      $footer.append(
        $("<span>").addClass("me-auto small text-muted").text(options.meta),
      );
    }
    $footer.append(
      $("<button>")
        .attr({ type: "button", "data-bs-dismiss": "modal" })
        .addClass("btn btn-outline-secondary")
        .text(options.closeLabel),
    );
    const $modal = $("<div>")
      .addClass("modal")
      .addClass("fade")
      .attr({
        id,
        tabindex: -1,
        role: "dialog",
        "aria-labelledby": titleId,
        "aria-hidden": "true",
      })
      .append(
        $("<div>")
          .addClass(
            "modal-dialog modal-dialog-scrollable modal-dialog-centered",
          )
          .append(
            $("<div>")
              .addClass("modal-content")
              .append(
                $("<div>")
                  .addClass("modal-header")
                  .append(
                    $("<h5>")
                      .addClass("modal-title")
                      .attr("id", titleId)
                      .text(options.title),
                    $("<button>")
                      .attr({
                        type: "button",
                        "data-bs-dismiss": "modal",
                        "aria-label": options.closeLabel,
                      })
                      .addClass("btn-close"),
                  ),
                $("<div>").addClass("modal-body").append(table(options)),
                $footer,
              ),
          ),
      );
    $("body").append($modal);
    $modal.on("hidden.bs.modal", () => $modal.remove());
    new bootstrap.Modal($modal[0]).show();
  }

  return { render, openDetail };
})();
