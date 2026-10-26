/* Changed-row flash and polite live-region summary for auto-refreshing DataTables.
 *
 *   const live = BWTableLive.attach(dt, { rowKey, liveRegion, message });
 *   live.arm();           // call right before an automatic reload
 *
 * `rowKey(rowData)` returns a stable identity for a row. After an armed redraw, rows whose key is
 * new get `ar-flash`, cells whose text changed get `ar-flash`, and `message(added, removed)` (a
 * translated sentence, or "" for nothing) is written to `liveRegion`. A redraw the user caused
 * (sort, filter, page) is never armed, so it neither flashes nor announces.
 */
window.BWTableLive = (function () {
  function flash(el) {
    el.classList.remove("ar-flash");
    void el.offsetWidth;
    el.classList.add("ar-flash");
  }

  function snapshot(dt, rowKey) {
    const rows = new Map();
    dt.rows({ page: "current" }).every(function () {
      const node = this.node();
      if (!node) return;
      rows.set(String(rowKey(this.data())), {
        node,
        cells: Array.from(node.cells, (cell) => cell.textContent),
      });
    });
    return rows;
  }

  function attach(dt, { rowKey, liveRegion, message }) {
    let previous = null;
    let armed = false;
    dt.on("draw.dt", () => {
      const current = snapshot(dt, rowKey);
      if (armed && previous) {
        let added = 0;
        current.forEach((row, key) => {
          const before = previous.get(key);
          if (!before) {
            added++;
            flash(row.node);
            return;
          }
          row.cells.forEach((text, index) => {
            if (text !== before.cells[index]) flash(row.node.cells[index]);
          });
        });
        let removed = 0;
        previous.forEach((_row, key) => {
          if (!current.has(key)) removed++;
        });
        if (liveRegion && (added || removed) && message) {
          liveRegion.textContent = message(added, removed);
        }
      }
      armed = false;
      previous = current;
    });
    return {
      arm() {
        armed = true;
      },
    };
  }

  return { attach };
})();
