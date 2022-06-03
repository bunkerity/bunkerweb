window.onload = init;

var darkMode = document.getElementById("dark-mode-switch");

var darkModeIcon = "darkModeIcon";

function init() {
  if (darkMode) {
    initTheme();
    darkMode.addEventListener("change", function () {
      resetTheme();
    });
  }
}

function initTheme() {
  var darkThemeSelected =
    window.matchMedia("(prefers-color-scheme: dark)").matches ||
    (localStorage.getItem("dark-mode") !== null &&
      localStorage.getItem("dark-mode") === "dark");

  darkMode.checked = darkThemeSelected;

  darkThemeSelected
    ? document.body.setAttribute("data-theme", "dark")
    : document.body.removeAttribute("data-theme");

  darkThemeSelected
    ? document.getElementById(darkModeIcon).classList.add("bi-moon")
    : document.getElementById(darkModeIcon).classList.add("bi-sun");
}

function resetTheme() {
  if (darkMode.checked) {
    document.body.setAttribute("data-theme", "dark");
    localStorage.setItem("dark-mode", "dark");
    document.getElementById(darkModeIcon).classList.remove("bi-sun");
    document.getElementById(darkModeIcon).classList.add("bi-moon");
  } else {
    document.body.removeAttribute("data-theme");
    localStorage.removeItem("dark-mode");
    document.getElementById(darkModeIcon).classList.remove("bi-moon");
    document.getElementById(darkModeIcon).classList.add("bi-sun");
  }
}
