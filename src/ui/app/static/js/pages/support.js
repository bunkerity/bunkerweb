$(document).ready(function () {
  const $serviceSearch = $("#service-search");
  const $serviceDropdownMenu = $("#services-dropdown-menu");
  const $serviceDropdownItems = $("#services-dropdown-menu li.nav-item");

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
