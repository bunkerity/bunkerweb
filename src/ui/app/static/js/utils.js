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
      $.getJSON("https://www.bunkerweb.io/api/posts/0/2")
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

      const cardText = $("<small>", { class: "card-text lh-1", text: excerpt });

      const cardFooter = $("<div>", {
        class:
          "card-footer p-0 mt-2 d-flex justify-content-between align-items-center",
      });
      $("<p>", { class: "card-text mb-0" })
        .append(
          $("<small>", { class: "text-muted", text: `Posted on: ${date}` }),
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
      const cardText = $("<p>", { class: "card-text", text: excerpt });

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
        $("<small>", { class: "text-muted", text: `Posted on: ${date}` }),
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
  const news = new News();
  news.init();
});
