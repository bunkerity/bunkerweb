document.addEventListener("DOMContentLoaded", function() {
  const tocNav = document.querySelector("nav.md-nav--secondary");
  if (!tocNav) return;

  const tocLinks = [];
  const dropdowns = []; // A list to hold all created dropdowns for the accordion effect

  // --- Step 1: Transform headers with children into dropdowns ---
  const parentItems = tocNav.querySelectorAll("li.md-nav__item:has(> nav.md-nav)");
  parentItems.forEach(item => {
    const link = item.querySelector(":scope > a.md-nav__link");
    const nestedNav = item.querySelector(":scope > nav.md-nav");
    if (!link || !nestedNav) return;

    const href = link.getAttribute("href");
    const details = document.createElement("details");
    details.classList.add("toc-dropdown");
    dropdowns.push(details); // Add to the list for the accordion

    const summary = document.createElement("summary");
    summary.classList.add("md-nav__link");
    summary.dataset.href = href; // Store href for the active state logic

    while (link.firstChild) {
      summary.appendChild(link.firstChild);
    }

    details.appendChild(summary);
    details.appendChild(nestedNav);

    // Add a click listener to the summary to handle navigation
    summary.addEventListener("click", () => {
      window.location.hash = href;
    });

    item.replaceChild(details, link);
    tocLinks.push(summary);
  });

  // --- Step 2: Implement the accordion logic ---
  dropdowns.forEach(currentDropdown => {
    currentDropdown.addEventListener('toggle', () => {
      if (!currentDropdown.open) return;

      const parentList = currentDropdown.parentElement?.parentElement;
      if (!parentList) return;

      Array.from(parentList.children).forEach(siblingItem => {
        if (!(siblingItem instanceof HTMLElement)) return;

        const siblingDropdown = siblingItem.querySelector('details.toc-dropdown');
        const isDirectChild = siblingDropdown?.parentElement === siblingItem;

        if (siblingDropdown && isDirectChild && siblingDropdown !== currentDropdown) {
          siblingDropdown.open = false;
        }
      });
    });
  });

  // --- Step 3: Collect all links and manage active state ---
  tocNav.querySelectorAll("a.md-nav__link").forEach(link => {
    if (link.tagName.toLowerCase() === 'a') {
      tocLinks.push(link);
    }
  });

  function updateActiveLink() {
    const currentHash = window.location.hash || "#";
    let activeElement = null;

    tocLinks.forEach(link => {
      const linkHref = link.dataset.href || link.getAttribute("href");
      if (linkHref === currentHash) {
        link.classList.add("md-nav__link--active");
        activeElement = link;
      } else {
        link.classList.remove("md-nav__link--active");
      }
    });

    // If the active link is inside a dropdown, make sure it's open
    if (activeElement) {
      const parentDetails = activeElement.closest("details.toc-dropdown");
      if (parentDetails && !parentDetails.open) {
        parentDetails.open = true;
      }
    }
  }

  function expandFirstDropdownIfNeeded() {
    if (window.location.hash) return; // Respect explicit anchors
    if (window.scrollY !== 0) return; // Only expand when the page loads at the top

    const firstDropdown = dropdowns[0];
    if (firstDropdown && !firstDropdown.open) {
      firstDropdown.open = true;
    }
  }

  window.addEventListener("hashchange", updateActiveLink);
  updateActiveLink(); // Set the correct state on initial page load
  expandFirstDropdownIfNeeded(); // Ensure the first dropdown is open when landing at the top
});
