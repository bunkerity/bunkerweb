export function getDarkMode() {
  let darkMode = false;
  console.log(sessionStorage.getItem("mode"));
  // Case on storage
  if (sessionStorage.getItem("mode")) {
    console.log("local");
    darkMode = sessionStorage.getItem("mode") === "dark" ? true : false;
  } else if (
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  ) {
    // dark mode
    darkMode = true;
    sessionStorage.setItem("mode", "dark");
  } else {
    darkMode = false;
    sessionStorage.setItem("mode", "light");
  }

  return darkMode;
}
