function throttle(func, limit, ...throttleArgs) {
  let inThrottle;
  return function (...args) {
    const context = this;
    if (!inThrottle) {
      func.apply(context, [...throttleArgs, ...args]);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

class News {
  constructor(t) {
    this.BASE_URL = "https://www.bunkerweb.io/";
    this.t = t;
  }

  init() {
    const lastRefetch = sessionStorage.getItem("lastRefetch");
    const nowStamp = Math.round(Date.now() / 1000);

    if (lastRefetch && nowStamp > lastRefetch) {
      sessionStorage.removeItem("lastRefetch");
      sessionStorage.removeItem("lastNews");
    }

    const lastNews = sessionStorage.getItem("lastNews");

    if (lastNews && lastNews !== "undefined") {
      this.render(JSON.parse(lastNews));
    } else {
      $.getJSON(
        "https://www.bunkerweb.io/wp-json/wp/v2/posts?_embed&per_page=4&orderby=date&order=desc",
      )
        .done((res) => {
          const reverseData = res.reverse();
          this.render(reverseData);
        })
        .fail((e) => {
          console.error("Failed to fetch news:", e);
        });
    }
  }

  render(lastNews) {
    if (
      !sessionStorage.getItem("lastNews") &&
      !sessionStorage.getItem("lastRefetch")
    ) {
      sessionStorage.setItem(
        "lastRefetch",
        Math.round(Date.now() / 1000) + 3600,
      );
      sessionStorage.setItem("lastNews", JSON.stringify(lastNews));

      const newsNumber = lastNews.length;
      $("#news-pill").append(
        DOMPurify.sanitize(
          `<span class="badge rounded-pill badge-center-sm bg-danger ms-1_5">${newsNumber}</span>`,
        ),
      );
      $("#news-button").after(
        DOMPurify.sanitize(
          `<span class="badge-dot-text position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger">${newsNumber}<span class="visually-hidden" data-i18n="badge.unread_news">${this.t(
            "badge.unread_news",
          )}</span></span>`,
        ),
      );
    }

    const newsContainer = $("#data-news-container").empty();
    const homeNewsContainer = $("#data-news-container-home");
    if (homeNewsContainer) {
      homeNewsContainer.empty();
    }

    const orderedNews = [...lastNews].reverse();
    const lastItem = orderedNews[orderedNews.length - 1];

    const newsRow = $("<div>", {
      "data-news-row": "",
      class: "row g-6 justify-content-center",
    }).appendTo(newsContainer);
    let homeNewsRow;

    if (homeNewsContainer) {
      homeNewsRow = $("<div>", {
        "data-news-row-home": "",
        class: "row g-2 justify-content-center",
      }).appendTo(homeNewsContainer);
    }

    orderedNews.forEach((news) => {
      const isLast = news === lastItem;

      const filteredTitle = news.title.rendered
        .trim()
        .replace(/^<p>([\s\S]*?)<\/p>$/i, "$1");
      const decodedTitle = $("<textarea/>").html(filteredTitle).text();

      const filteredExcerpt = news.excerpt.rendered
        .trim()
        .replace(/^<p>([\s\S]*?)<\/p>$/i, "$1");
      const decodedExcerpt = $("<textarea/>").html(filteredExcerpt).text();

      const articleTags = this.extractTerms(news);
      const formattedDate = this.formatDate(news.date);
      const featuredMedia = news._embedded?.["wp:featuredmedia"]?.[0] ?? null;
      const featuredImg = featuredMedia?.source_url ?? null;
      const featuredAlt =
        featuredMedia?.alt_text ||
        featuredMedia?.title?.rendered ||
        this.t("news.image_alt");

      // Render for sidebar/news page
      const cardElement = this.template(
        decodedTitle,
        news.link,
        featuredImg,
        featuredAlt,
        decodedExcerpt,
        articleTags,
        formattedDate,
        isLast,
        false,
      );
      newsRow.append(cardElement);

      if (homeNewsContainer) {
        // Render for home page
        const homeCardElement = this.template(
          decodedTitle,
          news.link,
          featuredImg,
          featuredAlt,
          decodedExcerpt,
          articleTags,
          formattedDate,
          isLast,
          true,
        );
        homeNewsRow.append(homeCardElement);
      }
    });
  }

  template(title, link, img, imgAlt, excerpt, tags, date, last, isHome) {
    const colClass = !isHome && last ? "" : "mb-1";
    const colSize = isHome ? "col-md-12 col-xl-12" : "col-md-11 col-xl-11";
    const col = $("<div>", {
      class: `${colSize} ${colClass}`,
    });

    const card = $("<div>", { class: "card" });
    const imageSrc = img ?? null;

    if (isHome) {
      // Home page layout with image on the left
      const row = $("<div>", {
        class: "row g-0 align-items-center",
      });

      if (imageSrc) {
        const imgCol = $("<div>", { class: "col-md-5" }).appendTo(row);
        const imgLink = $("<a>", {
          class: "w-100",
          href: `${link}?utm_campaign=self&utm_source=ui`,
          target: "_blank",
          rel: "noopener",
        }).append(
          $("<img>", {
            class: "card-img card-img-left",
            src: imageSrc,
            alt: imgAlt,
            loading: "lazy",
          }),
        );
        imgCol.append(imgLink);
      }

      const contentColClass = imageSrc ? "col-md-7" : "col-12";
      const contentCol = $("<div>", { class: contentColClass }).appendTo(row);
      const cardBody = $("<div>", { class: "card-body p-3" }).appendTo(
        contentCol,
      );

      const cardTitle = $("<h6>", { class: "card-title lh-sm mb-2" }).append(
        $("<a>", {
          href: `${link}?utm_campaign=self&utm_source=ui`,
          target: "_blank",
          rel: "noopener",
          text: title,
        }),
      );

      const cardText = $("<small>", {
        class: "card-text lh-1 courier-prime",
        text: excerpt,
      });

      const cardFooter = $("<div>", {
        class:
          "card-footer p-0 mt-3 d-flex justify-content-between align-items-center",
      });
      $("<p>", { class: "card-text mb-0" })
        .append(
          $("<small>", {
            class: "text-muted courier-prime",
            text: `Posted on: ${date}`,
          }),
        )
        .appendTo(cardFooter);

      const tagsContainer = $("<p>", { class: "d-flex flex-wrap m-0" });
      const validTags = tags.filter((tag) => tag?.slug && tag?.name);
      validTags.forEach((tag) => {
        $("<a>", {
          role: "button",
          href: `${this.BASE_URL}category/${tag.slug}?utm_campaign=self&utm_source=ui`,
          "aria-pressed": "true",
          class: "btn btn-xs btn-outline-primary",
          target: "_blank",
          rel: "noopener",
        })
          .append(
            $("<span>", {
              class: "tf-icons bx bx-xs bx-purchase-tag me-1",
            }),
            tag.name,
          )
          .appendTo(tagsContainer);
      });

      if (validTags.length) {
        tagsContainer.appendTo(cardFooter);
      }

      cardBody.append(cardTitle, cardText, cardFooter);
      card.append(row);
    } else {
      // Sidebar/news page layout with image on top
      if (imageSrc) {
        const imgLink = $("<a>", {
          href: `${link}?utm_campaign=self&utm_source=ui`,
          target: "_blank",
          rel: "noopener",
        }).append(
          $("<img>", {
            class: "card-img-top",
            src: imageSrc,
            alt: imgAlt,
            loading: "lazy",
          }),
        );
        card.append(imgLink);
      }

      const cardBody = $("<div>", { class: "card-body" });
      const cardTitle = $("<h5>", { class: "card-title" }).append(
        $("<a>", {
          href: `${link}?utm_campaign=self&utm_source=ui`,
          target: "_blank",
          rel: "noopener",
          text: title,
        }),
      );
      const cardText = $("<p>", {
        class: "card-text courier-prime",
        text: excerpt,
      });

      const tagsContainer = $("<p>", { class: "d-flex flex-wrap" });
      const validTags = tags.filter((tag) => tag?.slug && tag?.name);
      validTags.forEach((tag) => {
        $("<a>", {
          role: "button",
          href: `${this.BASE_URL}category/${tag.slug}?utm_campaign=self&utm_source=ui`,
          "aria-pressed": "true",
          class: "btn btn-sm btn-outline-primary",
          target: "_blank",
          rel: "noopener",
        })
          .append(
            $("<span>", {
              class: "tf-icons bx bx-xs bx-purchase-tag bx-18px me-2",
            }),
            tag.name,
          )
          .appendTo(tagsContainer);
      });

      const dateText = $("<p>", { class: "card-text" }).append(
        $("<small>", {
          class: "text-muted courier-prime",
          text: `Posted on: ${date}`,
        }),
      );

      if (validTags.length) {
        cardBody.append(cardTitle, cardText, tagsContainer, dateText);
      } else {
        cardBody.append(cardTitle, cardText, dateText);
      }
      card.append(cardBody);
    }

    if (isHome) {
      col.append(card);
    } else {
      col.append(card);
    }

    return col;
  }

  extractTerms(news) {
    const embeddedTerms = news._embedded?.["wp:term"] ?? [];
    const termMap = new Map();

    embeddedTerms
      .flat()
      .filter(
        (term) =>
          term &&
          (term.taxonomy === "category" || term.taxonomy === "post_tag") &&
          term.slug &&
          term.name,
      )
      .forEach((term) => {
        if (!termMap.has(term.slug)) {
          termMap.set(term.slug, { slug: term.slug, name: term.name });
        }
      });

    return Array.from(termMap.values());
  }

  formatDate(dateString) {
    if (!dateString) {
      return "";
    }

    const parsedDate = new Date(dateString);
    if (Number.isNaN(parsedDate.getTime())) {
      return dateString;
    }

    return parsedDate.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  }
}

// Initialize the News class
$(document).ready(() => {
  // Ensure i18next is loaded before using it
  const t = typeof i18next !== "undefined" ? i18next.t : (key) => key; // Fallback

  // Define news items array
  let newsItemsKeys = [
    "banner.pro",
    "banner.support",
    "banner.community", // Example keys
  ];
  // Store the original English fallbacks if needed, or rely on i18next fallbacks
  const newsItemFallbacks = {
    "banner.pro": `Get the most of BunkerWeb by upgrading to the PRO version. More info and free trial <a class="light-href text-white-80" target="_blank" rel="noopener" href="https://panel.bunkerweb.io/?utm_campaign=self&utm_source=banner#pro">here</a>.`,
    "banner.support": `Need premium support or tailored consulting around BunkerWeb? Check out our <a class="light-href text-white-80" target="_blank" rel="noopener" href="https://panel.bunkerweb.io/?utm_campaign=self&utm_source=banner#services">professional services</a>.`,
    "banner.community": `Be part of the Bunker community by joining the <a class="light-href text-white-80" target="_blank" rel="noopener" href="https://discord.bunkerweb.io/?utm_campaign=self&utm_source=banner">Discord chat</a> and following us on <a class="light-href text-white-80" target="_blank" rel="noopener" href="https://www.linkedin.com/company/bunkerity/">LinkedIn</a>.`,
  };

  let currentIndex = 0;
  const intervalTime = 7000;
  let interval;
  const $bannerText = $("#banner-text");
  const dbReadOnly = $("#db-read-only").val().trim() === "True";

  function calculateMinHeight() {
    // Create a hidden element to measure the max height
    const $measuringElement = $("<div>")
      .css({
        position: "absolute",
        visibility: "hidden",
        height: "auto",
        width: $bannerText.width(), // Set width to match the current width of the banner text container
        whiteSpace: "normal", // Change to normal for wrapping if needed
      })
      .appendTo("body");

    // Calculate the minimum height required for the banner text
    let minHeight = 0;
    newsItemsKeys.forEach((key) => {
      const translatedText = t(key, {
        defaultValue: newsItemFallbacks[key] || key,
      });
      $measuringElement.html(translatedText);
      minHeight = Math.max(minHeight, $measuringElement.outerHeight());
    });

    // Set the minimum height to avoid layout shifts
    $bannerText.css("min-height", minHeight);

    // Remove the measuring element from the DOM
    $measuringElement.remove();
  }

  // Calculate the min-height on page load
  calculateMinHeight();

  // Recalculate the min-height on window resize
  $(window).on("resize", throttle(calculateMinHeight, 200));

  const news = new News(t);
  news.init();

  function loadData() {
    const nowStamp = Math.round(Date.now() / 1000);
    const bannerRefetch = sessionStorage.getItem("bannerRefetch");
    let bannerNews = sessionStorage.getItem("bannerNews");

    // Check if cached data is expired
    if (bannerRefetch && nowStamp > bannerRefetch) {
      sessionStorage.removeItem("bannerRefetch");
      sessionStorage.removeItem("bannerNews");
      bannerNews = null;
    }

    if (bannerNews) {
      // Use cached data
      const data = JSON.parse(bannerNews);
      newsItemsKeys = data.map((item) => item.key);
    } else {
      // console.log("TODO: Fetch data from API when endpoint is available");
      // TODO: Fetch data from API when endpoint is available
      /*
      $.getJSON("https://www.bunkerweb.io/api/bw-ui-news-16")
        .done(function (res) {
          const data = res.data[0].data;
          sessionStorage.setItem("bannerNews", JSON.stringify(data));
          sessionStorage.setItem("bannerRefetch", nowStamp + 3600); // Refetch after one hour
          newsItemsKeys = data.map((item) => item.key);
        })
        .fail(function (e) {
          console.error("Failed to fetch banner news:", e);
        });
      */
    }
    newsItemsKeys.sort(() => Math.random() - 0.5);
    startInterval();
  }

  // Function to update the banner text with animation
  function updateBannerText(nextIndex) {
    // Remove any existing slide-in class to reset
    $bannerText.removeClass("slide-in").addClass("slide-out");

    setTimeout(() => {
      $bannerText.removeClass("slide-out");

      const currentKey = newsItemsKeys[nextIndex];
      const translatedText = t(currentKey, {
        defaultValue: newsItemFallbacks[currentKey] || currentKey,
      });

      // Update the text content
      const sanitizedText = DOMPurify.sanitize(translatedText, {
        USE_PROFILES: { html: true },
      });
      $bannerText.html(sanitizedText);

      // Trigger reflow to ensure the browser applies the changes
      $bannerText[0].offsetHeight;

      // Add the slide-in class to start the animation
      $bannerText.addClass("slide-in");
    }, 700);
  }

  // Function to start the automatic news rotation
  function startInterval() {
    if (newsItemsKeys.length > 0) {
      interval = setInterval(() => {
        currentIndex = (currentIndex + 1) % newsItemsKeys.length;
        updateBannerText(currentIndex);
      }, intervalTime);
    }
  }

  // Reset interval when user interacts
  function resetInterval() {
    clearInterval(interval);
    startInterval();
  }

  // Click event handler for the "next-news" icon
  $("#next-news").on("click", function () {
    currentIndex = (currentIndex + 1) % newsItemsKeys.length;
    updateBannerText(currentIndex);
    resetInterval();
  });

  if ($bannerText.length) {
    loadData();
    if (newsItemsKeys.length > 0) {
      // Initial display using the first key
      updateBannerText(0);
    }
  }

  var notificationsRead =
    parseInt(sessionStorage.getItem("notificationsRead")) || 0;

  function updateNotificationsBadge() {
    const $notificationsBadge = $("#unread-notifications");
    let unreadNotifications = parseInt($notificationsBadge.text());

    unreadNotifications = isNaN(unreadNotifications) ? 0 : unreadNotifications;

    if ($notificationsBadge.length) {
      const updatedUnread = unreadNotifications - notificationsRead;
      if (updatedUnread > 0) {
        $notificationsBadge.text(updatedUnread);
        $notificationsBadge.removeClass("d-none");
      } else {
        $notificationsBadge.addClass("d-none");
      }
    }
  }

  updateNotificationsBadge();

  $("#notifications-button").on("click", function () {
    const readNotifications = $(
      "#notifications-toast-container .bs-toast",
    ).length;
    notificationsRead = readNotifications;
    sessionStorage.setItem("notificationsRead", notificationsRead);
    updateNotificationsBadge();
  });

  // Debounced clear notifications logic
  const clearNotifications = debounce((rootUrl) => {
    const csrfToken = $("#csrf_token").val();
    const data = new FormData();
    data.append("csrf_token", csrfToken);

    if (!rootUrl) {
      return;
    }

    fetch(rootUrl.replace(/\/profile$/, "/clear_notifications"), {
      method: "POST",
      credentials: "same-origin",
      body: data,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Network response was not ok");
        }
        $("#notifications-toast-container").empty();
        sessionStorage.setItem("notificationsRead", 0);
        updateNotificationsBadge();
        $("#clear-notifications-btn").closest(".d-flex").hide();
        $(
          "#data-notifications-container p[data-i18n='status.no_notifications']",
        )
          .removeClass("d-none")
          .show();
      })
      .catch((error) => {
        console.error(
          "There was a problem with the clear notifications operation:",
          error,
        );
      });
  }, 300);

  $(document).on("click", "#clear-notifications-btn", function () {
    clearNotifications($(this).data("root-url"));
  });

  const saveTheme = debounce((rootUrl, theme) => {
    const csrfToken = $("#csrf_token").val();

    const data = new FormData();
    data.append("theme", theme);
    data.append("csrf_token", csrfToken);

    fetch(rootUrl, {
      method: "POST",
      body: data,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Network response was not ok");
        }
        // Handle success, redirect, etc.
      })
      .catch((error) => {
        console.error("There was a problem with the fetch operation:", error);
      });
  }, 1000);

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
    applyTheme(theme, $(this).data("root-url"));
  });

  // Function to apply the theme
  function applyTheme(theme, rootUrl = null) {
    $themeSelector = $("#theme-toggle");

    if (theme === "dark") {
      $("html")
        .removeClass("light-style")
        .addClass("dark-style dark")
        .attr("data-bs-theme", "dark");
      $(".btn-outline-dark")
        .addClass("btn-outline-light")
        .removeClass("btn-outline-dark");
      $(".btn-dark").addClass("btn-light").removeClass("btn-dark");
      $(".bg-white").addClass("bg-dark").removeClass("bg-white");
      $(".bs-toast.bg-white").addClass("bg-dark").removeClass("bg-white");
      $(".bg-light-subtle")
        .addClass("bg-dark-subtle")
        .removeClass("bg-light-subtle");
      $(".dark-mode-toggle-icon").removeClass("bx-sun").addClass("bx-moon");
      $("#dark-mode-toggle").prop("checked", true);
      $("[alt='BunkerWeb logo']").attr("src", $("#bw-logo-white").val());
      $("[alt='User Avatar']").attr("src", $("#avatar-url-white").val());
      $themeSelector.find("option[value='dark']").prop("selected", true);
    } else {
      $("html")
        .removeClass("dark-style dark")
        .addClass("light-style")
        .attr("data-bs-theme", null);
      $(".btn-outline-light")
        .addClass("btn-outline-dark")
        .removeClass("btn-outline-light");
      $(".bs-toast.bg-dark").addClass("bg-white").removeClass("bg-dark");
      $(".btn-light").addClass("btn-dark").removeClass("btn-light");
      $(".bg-dark").addClass("bg-white").removeClass("bg-dark");
      $(".bg-dark-subtle")
        .addClass("bg-light-subtle")
        .removeClass("bg-dark-subtle");
      $(".dark-mode-toggle-icon").removeClass("bx-moon").addClass("bx-sun");
      $("#dark-mode-toggle").prop("checked", false);
      $("[alt='BunkerWeb logo']").attr("src", $("#bw-logo").val());
      $("[alt='User Avatar']").attr("src", $("#avatar-url").val());
      $themeSelector.find("option[value='light']").prop("selected", true);
    }

    // Update input values
    $("#theme").val(theme);
    $("[name='theme']").val(theme);
    localStorage.setItem("theme", theme); // Save user preference

    if (!rootUrl || window.location.pathname.includes("/setup") || dbReadOnly)
      return;

    saveTheme(rootUrl.replace(/\/profile$/, "/set_theme"), theme);
  }

  $("#pluginsCollapse").on("show.bs.collapse", function () {
    sessionStorage.setItem("pluginsCollapse", "show");
  });

  $("#pluginsCollapse").on("hide.bs.collapse", function () {
    sessionStorage.setItem("pluginsCollapse", "hide");
  });

  const pluginsCollapse = sessionStorage.getItem("pluginsCollapse");
  if (pluginsCollapse === "hide") {
    $("#pluginsCollapse").collapse("hide");
  }

  $("#extraPagesCollapse").on("show.bs.collapse", function () {
    sessionStorage.setItem("extraPagesCollapse", "show");
  });

  $("#extraPagesCollapse").on("hide.bs.collapse", function () {
    sessionStorage.setItem("extraPagesCollapse", "hide");
  });

  const extraPagesCollapse = sessionStorage.getItem("extraPagesCollapse");
  if (extraPagesCollapse === "hide") {
    $("#extraPagesCollapse").collapse("hide");
  }

  $("#feedback-toast-container .bs-toast").each(function () {
    const toast = new bootstrap.Toast(this);
    toast.show();
  });

  i18next.on("languageChanged", () => {
    if ($bannerText.length && newsItemsKeys.length > 0) {
      updateBannerText(currentIndex); // Re-translate the current banner item
    }
  });
});
