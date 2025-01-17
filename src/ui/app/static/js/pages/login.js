$(document).ready(() => {
  // Check if there's a saved theme preference in localStorage
  let savedTheme = localStorage.getItem("theme");

  if (!savedTheme) {
    // If no saved preference, use the system's preferred color scheme
    const systemPrefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)",
    ).matches;
    savedTheme = systemPrefersDark ? "dark" : "light";
  }

  // Apply the saved or system-preferred theme
  applyTheme(savedTheme);

  // Toggle theme on change
  $("#dark-mode-toggle").on("change", function () {
    const darkMode = $(this).prop("checked");
    const theme = darkMode ? "dark" : "light";
    applyTheme(theme);
    localStorage.setItem("theme", theme); // Save user preference
  });

  // Function to apply the theme
  function applyTheme(theme) {
    if (theme === "dark") {
      $("html")
        .removeClass("light-style")
        .addClass("dark-style dark")
        .attr("data-bs-theme", "dark");
      $(".bs-toast.bg-white").addClass("bg-dark").removeClass("bg-white");
      $(".bg-light-subtle")
        .addClass("bg-dark-subtle")
        .removeClass("bg-light-subtle");
      $("#dark-mode-toggle").prop("checked", true);
      $("[alt='BunkerWeb logo']").attr("src", $("#bw-logo-white").val());
      $("[alt='User Avatar']").attr("src", $("#avatar-url-white").val());
    } else {
      $("html")
        .removeClass("dark-style dark")
        .addClass("light-style")
        .attr("data-bs-theme", null);
      $(".bs-toast.bg-dark").addClass("bg-white").removeClass("bg-dark");
      $(".bg-dark-subtle")
        .addClass("bg-light-subtle")
        .removeClass("bg-dark-subtle");
      $("#dark-mode-toggle").prop("checked", false);
      $("[alt='BunkerWeb logo']").attr("src", $("#bw-logo").val());
      $("[alt='User Avatar']").attr("src", $("#avatar-url").val());
    }

    // Update input values
    $("#theme").val(theme);
    $("[name='theme']").val(theme);
  }
});
