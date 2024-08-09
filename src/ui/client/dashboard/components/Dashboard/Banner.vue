<script setup>
import { onMounted, reactive } from "vue";
import { useBannerStore } from "@store/global.js";
import { bannerIndex } from "@utils/tabindex.js";
import { computed } from "vue";

/**
 * @name Dashboard/Banner.vue
 *@description This component is a banner that display news.
 * The banner will display news from the api if available, otherwise it will display default news.
 */

const bannerStore = useBannerStore();

const banner = reactive({
  visibleId: 1,
  default: [
    {
      title:
        "Get the most of BunkerWeb by upgrading to the PRO version. More info and free trial",
      link: "https://panel.bunkerweb.io/?utm_campaign=self&utm_source=ui#pro",
      linkText: "here",
    },
    {
      title:
        "Need premium support or tailored consulting around BunkerWeb ? Check out our",
      link: "https://panel.bunkerweb.io/?utm_campaign=self&utm_source=ui#services",
      linkText: "professional services.",
    },
    {
      title: "Be part of the Bunker community by joining the",
      link: "Discord chat.",
      linkText: "https://discord.bunkerweb.io",
    },
  ],
  isTabIndex: false,
  api: [],
  apiFormat: computed(() => {
    if (banner.api.length === 0) return [];
    // deep copy
    const data = JSON.parse(JSON.stringify(banner.api));
    data.forEach((item, index) => {
      // I want to match everything inside class and replace it
      data[index].content = item.content.replace(
        /class='(.+?)'|class="(.+?)"/g,
        'class="banner-item-text"',
      );
    });
    return data;
  }),
});

/**
 *@name setupBanner
 * @description This function will try to retrieve banner news from the local storage, and in case it is not available or older than one hour, it will fetch the news from the api.
 * @returns {void}
 */
function setupBanner() {
  // Check if data, and if case, that data is not older than one hour
  // Case it is, refetch
  if (sessionStorage.getItem("bannerRefetch") !== null) {
    const storeStamp = sessionStorage.getItem("bannerRefetch");
    const nowStamp = Math.round(new Date().getTime() / 1000);
    if (+nowStamp > storeStamp) {
      sessionStorage.removeItem("bannerRefetch");
      sessionStorage.removeItem("bannerNews");
    }
  }
  // Case we already have the data
  if (sessionStorage.getItem("bannerNews") !== null) {
    banner.api = JSON.parse(sessionStorage.getItem("bannerNews"));
    banner.default = [];
    runBanner();
    return;
  }
  // Try to fetch api data
  fetch("https://www.bunkerweb.io/api/bw-ui-news")
    .then((res) => {
      return res.json();
    })
    .then((res) => {
      sessionStorage.setItem("bannerNews", JSON.stringify(res.data[0].data));
      // Refetch after one hour
      sessionStorage.setItem(
        "bannerRefetch",
        Math.round(new Date().getTime() / 1000) + 3600,
      );
      banner.api = res.data[0].data;
      if (banner.api.length > 0) {
        banner.default = [];
      }
      runBanner();
    })
    .catch((e) => {
      console.error(e);
      runBanner();
    });
}

/**
 * @name runBanner
 * @description Run the banner animation to display all news at a regular interval.
 * @returns {void}
 */
function runBanner() {
  const nextDelay = 8000;
  const transDuration = 1000;
  // Switch item every interval and
  setTimeout(() => {
    const prev = banner.visibleId;
    banner.visibleId = banner.visibleId === 2 ? 0 : banner.visibleId + 1;
    const next = banner.visibleId;

    // Hide previous one
    const oldItem = document.getElementById(`banner-item-${prev}`);
    oldItem.classList.add("-left-full");
    oldItem.classList.remove("left-0");
    setTimeout(() => {
      oldItem.classList.remove("transition-all");
    }, transDuration + 10);
    setTimeout(() => {
      oldItem.classList.add("opacity-0");
    }, transDuration + 30);
    setTimeout(() => {
      oldItem.classList.remove("-left-full");
      oldItem.classList.add("left-full");
    }, transDuration * 2);

    // Show new one
    const newItem = document.getElementById(`banner-item-${next}`);
    newItem.classList.remove("opacity-0");
    newItem.classList.add("transition-all");
    newItem.classList.add("left-0");
    newItem.classList.remove("left-full");

    runBanner();
  }, nextDelay);
}

/**
 * @name observeBanner
 * @description Check if the banner is visible in the viewport and set the state in the global bannerStore to update related components.
 **  @returns {void}
 */
function observeBanner() {
  const options = {
    root: null,
    rootMargin: "0px",
    threshold: 0.35,
  };

  const observer = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) bannerStore.setBannerVisible(true);
      if (!entry.isIntersecting) bannerStore.setBannerVisible(false);
    });
  }, options);

  observer.observe(document.getElementById("banner"));
}

/**
 * @name noTabindex
 * @description Stop highlighting a banner item that was focused with tabindex.
 * @returns {void}
 */
function noTabindex() {
  const bannerItems = document.querySelectorAll(".banner-item");
  bannerItems.forEach((item) => {
    item.classList.remove("banner-tabindex-highlight", "banner-tabindex-hide");
  });
}

/**
 * @name isTabindex
 * @description Highlighting a banner item that is focused with tabindex.
 * @returns {void}
 */
function isTabindex() {
  const activeElement = document.activeElement;
  const bannerItems = document.querySelectorAll(".banner-item");
  bannerItems.forEach((item) => {
    item.classList.add("banner-tabindex-hide");
    item.classList.remove("banner-tabindex-highlight");
  });
  // Higher z-index for the focused element
  activeElement
    .closest(".banner-item")
    .classList.add("banner-tabindex-highlight");
  activeElement
    .closest(".banner-item")
    .classList.remove("banner-tabindex-hide");
}

/**
 **  @name isTabindex
 **  @description Focus with tabindex break banner animation.
 * When a banner is focused, we need to add in front of the current banner the focus element.
 * And remove it when the focus is lost.
 * @returns {void}
 */
function handleTabIndex() {
  // Get the active element after tabindex click
  document.addEventListener("keyup", (e) => {
    if (
      e.key !== "Tab" &&
      !document.activeElement.classList.contains("banner-item-text")
    )
      return;
    if (document.activeElement.classList.contains("banner-item-text")) {
      isTabindex();
      return;
    } else {
      noTabindex();
    }
  });
}

onMounted(() => {
  observeBanner();
  setupBanner();
  handleTabIndex();
});
</script>

<template>
  <div id="banner" role="list" class="banner-container">
    <div role="img" aria-hidden="true" class="banner-bg"></div>
    <div
      v-for="(bannerEl, index) in banner.default"
      role="listitem"
      :id="`banner-item-${index}`"
      class="banner-item"
      :class="[index === 1 ? 'left-0' : 'left-full opacity-0']"
    >
      <p class="banner-item-text">
        {{ bannerEl.title }}
        <a
          :tabindex="bannerIndex"
          class="banner-item-link"
          :href="bannerEl.link"
        >
          {{ bannerEl.linkText }}
        </a>
      </p>
    </div>
    <div
      v-for="(bannerEl, index) in banner.apiFormat"
      role="listitem"
      :id="`banner-item-${index}`"
      class="banner-item"
      :class="[index === 1 ? 'left-0' : 'left-full opacity-0']"
    >
      <div v-html="bannerEl.content"></div>
    </div>
  </div>
</template>
