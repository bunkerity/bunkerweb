class News {
  constructor() {
    this.BASE_URL = "https://www.bunkerweb.io/";
  }

  init() {
    const lastRefetch = sessionStorage.getItem("lastRefetch");
    const nowStamp = Math.round(Date.now() / 1000);

    if (lastRefetch && nowStamp > lastRefetch) {
      sessionStorage.removeItem("lastRefetch");
      sessionStorage.removeItem("lastNews");
    }

    const lastNews = sessionStorage.getItem("lastNews");

    if (lastNews) {
      this.render(JSON.parse(lastNews));
    } else {
      $.getJSON("https://www.bunkerweb.io/api/posts/0/3")
        .done((res) => {
          const reverseData = res.data.reverse();
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
          `<span class="badge-dot-text position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger">${newsNumber}<span class="visually-hidden">unread news</span></span>`,
        ),
      );
    }

    const newsContainer = $("#data-news-container").empty();
    const homeNewsContainer = $("#data-news-container-home");
    if (homeNewsContainer) {
      homeNewsContainer.empty();
    }
    const lastItem = lastNews[0];

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

    lastNews.reverse().forEach((news) => {
      const isLast = news === lastItem;

      // Render for sidebar/news page
      const cardElement = this.template(
        news.title,
        news.slug,
        news.photo.url,
        news.excerpt,
        news.tags,
        news.date,
        isLast,
        false, // isHome is false
      );
      newsRow.append(cardElement);

      if (homeNewsContainer) {
        // Render for home page
        const homeCardElement = this.template(
          news.title,
          news.slug,
          news.photo.url,
          news.excerpt,
          news.tags,
          news.date,
          isLast,
          true, // isHome is true
        );
        homeNewsRow.append(homeCardElement);
      }
    });
  }

  template(title, slug, img, excerpt, tags, date, last, isHome) {
    const colClass = !isHome && last ? "" : "mb-1";
    const colSize = isHome ? "col-md-12 col-xl-12" : "col-md-11 col-xl-11";
    const col = $("<div>", {
      class: `${colSize} ${colClass}`,
    });

    const card = $("<div>", { class: "card" });

    if (isHome) {
      // Home page layout with image on the left
      const row = $("<div>", {
        class: "row g-0 align-items-center",
      });

      const imgCol = $("<div>", { class: "col-md-5" }).appendTo(row);
      const imgLink = $("<a>", {
        class: "w-100",
        href: `${this.BASE_URL}blog/post/${slug}?utm_campaign=self&utm_source=ui`,
        target: "_blank",
        rel: "noopener",
      }).append(
        $("<img>", {
          class: "card-img card-img-left",
          src: img,
          alt: "News image",
        }),
      );
      imgCol.append(imgLink);

      const contentCol = $("<div>", { class: "col-md-7" }).appendTo(row);
      const cardBody = $("<div>", { class: "card-body p-3" }).appendTo(
        contentCol,
      );

      const cardTitle = $("<h6>", { class: "card-title lh-sm mb-2" }).append(
        $("<a>", {
          href: `${this.BASE_URL}blog/post/${slug}?utm_campaign=self&utm_source=ui`,
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
      tags.forEach((tag) => {
        $("<a>", {
          role: "button",
          href: `${this.BASE_URL}blog/tag/${tag.slug}?utm_campaign=self&utm_source=ui`,
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

      tagsContainer.appendTo(cardFooter);

      cardBody.append(cardTitle, cardText, cardFooter);
      card.append(row);
    } else {
      // Sidebar/news page layout with image on top
      const imgLink = $("<a>", {
        href: `${this.BASE_URL}blog/post/${slug}?utm_campaign=self&utm_source=ui`,
        target: "_blank",
        rel: "noopener",
      }).append(
        $("<img>", {
          class: "card-img-top",
          src: img,
          alt: "News image",
        }),
      );

      const cardBody = $("<div>", { class: "card-body" });
      const cardTitle = $("<h5>", { class: "card-title" }).append(
        $("<a>", {
          href: `${this.BASE_URL}blog/post/${slug}?utm_campaign=self&utm_source=ui`,
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
      tags.forEach((tag) => {
        $("<a>", {
          role: "button",
          href: `${this.BASE_URL}blog/tag/${tag.slug}?utm_campaign=self&utm_source=ui`,
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

      cardBody.append(cardTitle, cardText, tagsContainer, dateText);
      card.append(imgLink, cardBody);
    }

    if (isHome) {
      col.append(card);
    } else {
      col.append(card);
    }

    return col;
  }
}

// Initialize the News class
$(document).ready(() => {
  // Define news items array
  let newsItems = [
    `Get the most of BunkerWeb by upgrading to the PRO version. More info and free trial <a class="light-href text-white-80" target="_blank" rel="noopener" href="https://panel.bunkerweb.io/?utm_campaign=self&utm_source=banner#pro">here</a>.`,
    `Need premium support or tailored consulting around BunkerWeb? Check out our <a class="light-href text-white-80" target="_blank" rel="noopener" href="https://panel.bunkerweb.io/?utm_campaign=self&utm_source=banner#services">professional services</a>.`,
    `Be part of the Bunker community by joining the <a class="light-href text-white-80" target="_blank" rel="noopener" href="https://discord.bunkerweb.io/?utm_campaign=self&utm_source=banner">Discord chat</a> and following us on <a class="light-href text-white-80" target="_blank" rel="noopener" href="https://www.linkedin.com/company/bunkerity/">LinkedIn</a>.`,
  ];

  let currentIndex = 0;
  const intervalTime = 7000;
  let interval;
  const $bannerText = $("#banner-text");

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
    newsItems.forEach((item) => {
      $measuringElement.html(item);
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
  $(window).on("resize", function () {
    calculateMinHeight();
  });

  const news = new News();
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
      newsItems = data.map((item) => item.content);
    } else {
      console.log("TODO: Fetch data from API when endpoint is available");
      // TODO: Fetch data from API when endpoint is available
      /*
      $.getJSON("https://www.bunkerweb.io/api/bw-ui-news-16")
        .done(function (res) {
          const data = res.data[0].data;
          sessionStorage.setItem("bannerNews", JSON.stringify(data));
          sessionStorage.setItem("bannerRefetch", nowStamp + 3600); // Refetch after one hour
          newsItems = data.map((item) => item.content);
        })
        .fail(function (e) {
          console.error("Failed to fetch banner news:", e);
        });
      */
    }
    newsItems.sort(() => Math.random() - 0.5);
    startInterval();
  }

  // Function to update the banner text with animation
  function updateBannerText(nextIndex) {
    // Remove any existing slide-in class to reset
    $bannerText.removeClass("slide-in").addClass("slide-out");

    setTimeout(() => {
      $bannerText.removeClass("slide-out");

      // Update the text content
      $bannerText.html(newsItems[nextIndex]);

      // Trigger reflow to ensure the browser applies the changes
      $bannerText[0].offsetHeight;

      // Add the slide-in class to start the animation
      $bannerText.addClass("slide-in");
    }, 700);
  }

  // Function to start the automatic news rotation
  function startInterval() {
    if (newsItems.length > 0) {
      interval = setInterval(() => {
        currentIndex = (currentIndex + 1) % newsItems.length;
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
    currentIndex = (currentIndex + 1) % newsItems.length;
    updateBannerText(currentIndex);
    resetInterval();
  });

  if ($bannerText.length) {
    loadData();
    $("#next-news").trigger("click");
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

  $("#dark-mode-toggle").on("change", function () {
    // If endpoint is "setup", ignore the theme change
    if (window.location.pathname.includes("/setup")) return;

    const darkMode = $(this).prop("checked");
    if (darkMode) {
      $("html").removeClass("light-style").addClass("dark-style");
      $(".btn-outline-dark")
        .addClass("btn-outline-light")
        .removeClass("btn-outline-dark");
      $(".btn-dark").addClass("btn-light").removeClass("btn-dark");
      $(".bg-white").addClass("bg-dark").removeClass("bg-white");
      $(".bg-light-subtle")
        .addClass("bg-dark-subtle")
        .removeClass("bg-light-subtle");
      $("html").attr("data-bs-theme", "dark");
      $(".dark-mode-toggle-icon").removeClass("bx-sun").addClass("bx-moon");
      $("[alt='BunkerWeb logo']").attr("src", $("#bw-logo-white").val());
      $("[alt='User Avatar']").attr("src", $("#avatar-url-white").val());
    } else {
      $("html").removeClass("dark-style").addClass("light-style");
      $(".btn-outline-light")
        .addClass("btn-outline-dark")
        .removeClass("btn-outline-light");
      $(".btn-light").addClass("btn-dark").removeClass("btn-light");
      $(".bg-dark").addClass("bg-white").removeClass("bg-dark");
      $(".bg-dark-subtle")
        .addClass("bg-light-subtle")
        .removeClass("bg-dark-subtle");
      $("html").attr("data-bs-theme", null);
      $(".dark-mode-toggle-icon").removeClass("bx-moon").addClass("bx-sun");
      $("[alt='BunkerWeb logo']").attr("src", $("#bw-logo").val());
      $("[alt='User Avatar']").attr("src", $("#avatar-url").val());
    }

    $("#theme").val(darkMode ? "dark" : "light");

    const rootUrl = $(this)
      .data("root-url")
      .replace(/\/profile$/, "/set_theme");
    const csrfToken = $("#csrf_token").val();
    const theme = darkMode ? "dark" : "light";
    localStorage.setItem("theme", theme); // Save user preference

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
  });
});
