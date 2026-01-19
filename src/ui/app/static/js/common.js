// common.js

/**
 * Debounce function to limit the rate at which a function can fire.
 * @param {Function} func - The function to debounce.
 * @param {number} delay - The delay in milliseconds.
 * @returns {Function} Debounced function.
 */
function debounce(func, delay) {
  let timer = null;
  return (...args) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      func(...args);
    }, delay);
  };
}

function normalizeTitleSegment(segment) {
  return (segment || "").replace(/\s+/g, " ").trim();
}

function getBreadcrumbTitleParts() {
  const crumbs = document.querySelectorAll(".breadcrumb .breadcrumb-item a");
  if (!crumbs.length) {
    return [];
  }

  return Array.from(crumbs)
    .map((crumb) => normalizeTitleSegment(crumb.textContent))
    .filter((part) => part && part !== "/");
}

function getFallbackPageTitle() {
  const body = document.body;
  if (!body) {
    return "";
  }
  return normalizeTitleSegment(body.getAttribute("data-page-title"));
}

function updatePageTitle() {
  const appName = "BunkerWeb UI";
  const parts = getBreadcrumbTitleParts();
  const fallback = getFallbackPageTitle();
  const normalizedParts = parts.filter(
    (part, index) => part !== parts[index - 1],
  );

  let title = appName;
  if (normalizedParts.length) {
    title = `${normalizedParts.join(" - ")} - ${appName}`;
  } else if (fallback) {
    title = `${fallback} - ${appName}`;
  }

  if (document.title !== title) {
    document.title = title;
  }
}

window.updatePageTitle = updatePageTitle;

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", updatePageTitle);
} else {
  updatePageTitle();
}
