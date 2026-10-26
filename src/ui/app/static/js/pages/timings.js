// Timings: client toolbar over the rows the server already rendered (OPS-49). Search, phase filter,
// sortable headers, a Columns menu and a CSV export of what is on screen. No request is made.
(function () {
  const body = document.getElementById("timings-body");
  if (!body) return;

  const table = document.getElementById("timings-table");
  const search = document.getElementById("timings-search");
  const phase = document.getElementById("timings-phase");
  const count = document.getElementById("timings-count");
  const noMatch = document.getElementById("timings-nomatch");
  const rows = Array.from(body.querySelectorAll("tr[data-plugin]"));
  const state = { key: "total", dir: -1 };
  const textKeys = ["plugin", "phase"];

  const compare = (a, b) => {
    const left = a.dataset[state.key];
    const right = b.dataset[state.key];
    if (textKeys.includes(state.key))
      return left.localeCompare(right) * state.dir;
    // An empty share (phases that do not run per request) sorts below every real value.
    const x = left === "" ? -1 : parseFloat(left);
    const y = right === "" ? -1 : parseFloat(right);
    return (x - y) * state.dir;
  };

  function render() {
    const query = (search.value || "").trim().toLowerCase();
    const wanted = phase.value;
    let visible = 0;
    rows.sort(compare).forEach((row) => {
      const match =
        (!wanted || row.dataset.phase === wanted) &&
        (!query ||
          `${row.dataset.plugin} ${row.dataset.phase}`
            .toLowerCase()
            .includes(query));
      row.hidden = !match;
      if (match) visible += 1;
      body.insertBefore(row, noMatch);
    });
    noMatch.classList.toggle("d-none", visible > 0);
    count.textContent = String(visible);
    table.querySelectorAll("th[data-sort]").forEach((th) => {
      th.setAttribute(
        "aria-sort",
        th.dataset.sort === state.key
          ? state.dir < 0
            ? "descending"
            : "ascending"
          : "none",
      );
    });
  }

  table.querySelectorAll("th[data-sort]").forEach((th) => {
    const go = () => {
      const key = th.dataset.sort;
      state.dir =
        state.key === key ? -state.dir : textKeys.includes(key) ? 1 : -1;
      state.key = key;
      render();
    };
    th.addEventListener("click", go);
    th.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        go();
      }
    });
  });

  search.addEventListener("input", render);
  phase.addEventListener("change", render);

  document
    .querySelectorAll("#timings-columns input[data-col]")
    .forEach((box) => {
      box.addEventListener("change", () => {
        table
          .querySelectorAll(`[data-col="${box.dataset.col}"]`)
          .forEach((cell) => (cell.hidden = !box.checked));
      });
    });

  // CSV of the visible rows, raw seconds so a spreadsheet can sort them. A cell that starts
  // with a formula character is neutralised, as the DataTables exports do.
  const csvCell = (value) => {
    let text = String(value);
    if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
    return `"${text.replace(/"/g, '""')}"`;
  };
  document.getElementById("timings-export").addEventListener("click", () => {
    const head = [
      "plugin",
      "phase",
      "calls",
      "mean_s",
      "max_s",
      "total_s",
      "share_pct",
    ];
    const lines = [head.map(csvCell).join(",")];
    rows
      .filter((row) => !row.hidden)
      .forEach((row) => {
        const d = row.dataset;
        lines.push(
          [d.plugin, d.phase, d.calls, d.mean, d.max, d.total, d.share]
            .map(csvCell)
            .join(","),
        );
      });
    const blob = new Blob([lines.join("\r\n")], {
      type: "text/csv;charset=utf-8",
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "timings.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  });

  render();
})();
