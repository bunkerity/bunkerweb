<script setup>
const items = [
  {
    id: 0,
    text: "Need premium support ? Check BunkerWeb Panel",
    link: "https://panel.bunkerweb.io/?utm_campaign=self&utm_source=ui",
  },
  {
    id: 1,
    text: "Try BunkerWeb on our demo wep app !",
    link: "https://demo.bunkerweb.io/link/?utm_campaign=self&utm_source=ui",
  },
  {
    id: 2,
    text: "All informations about BunkerWeb on our website !",
    link: "https://www.bunkerweb.io/?utm_campaign=self&utm_source=ui",
  },
];

class Banner {
  constructor() {
    this.bannerEl = document.getElementById("banner");
    this.bannerItems = this.bannerEl.querySelectorAll('[role="listitem"]');
    this.nextDelay = 9000;
    this.transDuration = 700;
    this.menuBtn = document.querySelector("[data-sidebar-menu-toggle]");
    this.menuEl = document.querySelector("[data-sidebar-menu]");
    this.newsBtn = document.querySelector("[data-sidebar-info-open]");
    this.flashBtn = document.querySelector("[data-flash-group]");
    this.init();
  }

  init() {
    this.changeMenu();
    setInterval(() => {
      // Get current visible
      let visibleEl;
      this.bannerItems.forEach((item) => {
        if (item.getAttribute("aria-hidden") === "false") {
          visibleEl = item;
        }
      });

      // Get next one to show (next index or first one)
      let nextEl =
        this.bannerEl.querySelector(
          `[role="listitem"][data-id="${
            +visibleEl.getAttribute("data-id") + 1
          }"]`
        ) || this.bannerEl.querySelector(`[role="listitem"][data-id="0"]`);

      // Hide current one
      visibleEl.classList.add("-left-full");
      visibleEl.classList.remove("left-0");
      visibleEl.setAttribute("aria-hidden", "true");
      setTimeout(() => {
        visibleEl.classList.remove("transition-all");
      }, this.transDuration + 10);
      setTimeout(() => {
        visibleEl.classList.add("opacity-0");
      }, this.transDuration + 20);
      setTimeout(() => {
        visibleEl.classList.remove("-left-full");
        visibleEl.classList.add("left-full");
      }, this.transDuration * 2);

      // Show next one
      nextEl.classList.remove("opacity-0");
      nextEl.classList.add("transition-all");
      nextEl.classList.add("left-0");
      nextEl.classList.remove("left-full");
      nextEl.setAttribute("aria-hidden", "false");
    }, this.nextDelay);
  }

  changeMenu() {
    let options = {
      root: null,
      rootMargin: "0px",
      threshold: 0.35,
    };

    let observer = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          this.menuEl.classList.add("mt-[4.5rem]");
          this.menuBtn.classList.add("top-[8.2rem]", "sm:top-[4.5rem]");
          this.newsBtn.classList.add("top-[4.5rem]");
          this.flashBtn.classList.add("top-[4.5rem]");
          this.menuBtn.classList.remove("top-16", "sm:top-2");
          this.newsBtn.classList.remove("top-2");
          this.flashBtn.classList.remove("top-2");
          this.menuEl.classList.remove("mt-2");
        }

        if (!entry.isIntersecting) {
          this.menuEl.classList.add("mt-2");
          this.menuBtn.classList.add("top-16", "sm:top-2");
          this.newsBtn.classList.add("top-2");
          this.flashBtn.classList.add("top-2");
          this.menuBtn.classList.remove("top-[8.2rem]", "sm:top-[4.5rem]");
          this.newsBtn.classList.remove("top-[4.5rem]");
          this.flashBtn.classList.remove("top-[4.5rem]");
          this.menuEl.classList.remove("mt-[4.5rem]");
        }
      });
    }, options);

    observer.observe(this.bannerEl);
  }
}

onMounted(() => {
  new Banner();
});
</script>

<template>
  <div id="banner" tabindex="-1" role="list" class="banner-container">
    <div class="banner-bg"></div>

    <div
      v-for="item in items"
      role="listitem"
      aria-hidden="false"
      :id="`banner-item-${item.id}`"
      class="banner-item"
    >
      <p class="banner-item-text">
        {{ item.text }}
        <a
          class="banner-item-link"
          href="https://panel.bunkerweb.io/?utm_campaign=self&utm_source=ui"
        >
          {{ item.link }}
        </a>
      </p>
    </div>
  </div>
</template>
