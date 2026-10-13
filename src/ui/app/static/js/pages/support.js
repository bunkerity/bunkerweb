$(document).ready(function () {
  const $serviceSearch = $("#service-search");
  const $serviceDropdownMenu = $("#services-dropdown-menu");
  const $serviceDropdownItems = $("#services-dropdown-menu li.nav-item");

  // Unchecked asks the server for clear values (admin only, the server enforces it)
  $("#mask-passwords").on("change", function () {
    const mask = this.checked;
    $(".support-config-link").each(function () {
      const url = new URL(this.getAttribute("href"), window.location.origin);
      if (mask) url.searchParams.delete("mask_passwords");
      else url.searchParams.set("mask_passwords", "no");
      this.setAttribute("href", url.pathname + url.search);
    });
  });

  $("#select-service").on("click", () => $serviceSearch.focus());

  $serviceSearch.on(
    "input",
    debounce((e) => {
      const inputValue = e.target.value.toLowerCase();
      let visibleItems = 0;

      $serviceDropdownItems.each(function () {
        const item = $(this);
        const matches = item.text().toLowerCase().includes(inputValue);

        item.toggle(matches);

        if (matches) {
          visibleItems++; // Increment when an item is shown
        }
      });

      if (visibleItems === 0) {
        if ($serviceDropdownMenu.find(".no-service-items").length === 0) {
          $serviceDropdownMenu.append(
            '<li class="no-service-items dropdown-item text-muted">No Item</li>',
          );
        }
      } else {
        $serviceDropdownMenu.find(".no-service-items").remove();
      }
    }, 50),
  );

  $(document).on("hidden.bs.dropdown", "#select-service", function () {
    $("#service-search").val("").trigger("input");
  });
});
