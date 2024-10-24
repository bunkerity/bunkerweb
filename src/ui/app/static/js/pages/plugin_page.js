$(document).ready(function () {
  $(".date-field").each(function () {
    const isoDateStr = $(this).text().trim();

    if (isoDateStr == "N/A") return;

    // Parse the ISO format date string
    const date = new Date(isoDateStr);

    // Check if the date is valid
    if (!isNaN(date)) {
      // Convert to local date and time string
      const localDateStr = date.toLocaleString();

      // Update the text content with the local date string
      $(this).text(localDateStr);
    } else {
      // Handle invalid date
      console.error(`Invalid date string: ${isoDateStr}`);
    }
  });

  $(".table").each(function () {
    tableLength = parseInt($(`#${this.id}-length`).val().trim());

    var tableOrder;
    const $tableOrder = $(`#${this.id}-order`);
    if ($tableOrder.length) {
      tableOrder = JSON.parse($tableOrder.text().trim());
    } else {
      tableOrder = { column: 0, dir: "desc" };
    }

    var tableTypes;
    const $tableTypes = $(`#${this.id}-types`);
    if ($tableTypes.length) {
      tableTypes = JSON.parse($tableTypes.text().trim());
    }

    const layout = {
      topStart: {},
      bottomEnd: {},
    };

    if (tableLength > 10) {
      const menu = [10];
      if (tableLength > 25) {
        menu.push(25);
      }
      if (tableLength > 50) {
        menu.push(50);
      }
      if (tableLength > 100) {
        menu.push(100);
      }
      menu.push({ label: "All", value: -1 });
      layout.topStart.pageLength = {
        menu: menu,
      };
      layout.bottomEnd.paging = true;
    }

    const columnDefs = [];
    if (tableTypes) {
      Object.entries(tableTypes).forEach(([column, type]) => {
        columnDefs.push({
          type: type,
          targets: parseInt(column),
        });
      });
    }

    new DataTable(this, {
      columnDefs: columnDefs,
      autoFill: false,
      responsive: true,
      layout: layout,
      order: [[parseInt(tableOrder.column), tableOrder.dir]],
    });

    $(this).removeClass("d-none");
  });

  $(".dt-type-numeric").removeClass("dt-type-numeric");
});
