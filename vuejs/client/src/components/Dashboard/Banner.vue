<script setup>
import { onMounted, reactive } from "vue";
import { useBannerStore } from "@store/global.js";
import { bannerIndex } from "@utils/tabindex.js";
import { computed } from "vue";

/** 
  @name Dashboard/Banner.vue
  @description This component is a banner that display news.
  The banner will display news from the api if available, otherwise it will display default news.
*/

const bannerStore = useBannerStore();

const banner = reactive({
  visibleId: 1,
  default : [
    {
      title: "title_1",
      link: "link_1",
      linkText: "link_text_1",
    },
    {
      title: "title_2",
      link: "link_2",
      linkText: "link_text_2",
    },
    {
      title: "title_3",
      link: "link_3",
      linkText: "link_text_3",
    },
  ],
  api: [],
  apiFormat : computed(() => {
    if(banner.api.length === 0) return [];
    // deep copy
    const data = JSON.parse(JSON.stringify(banner.api));
      data.forEach((item, index) => {
      // I want to match everything inside class and replace it
      data[index].content = item.content.replace(/class='(.+?)'|class="(.+?)"/g, 'class="banner-item-text"');
    });
    return data
  }),
});

const data = [{
  "content": "<p class='p-0 mx-'>content_1</p>",
}]
// I want to replace the content class content by banner-item-text

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
      banner.api =
        JSON.parse(sessionStorage.getItem("bannerNews"))
        banner.default = [];
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
        if(banner.api.length > 0) {
          banner.default = [];
        }
        runBanner();
      })
      .catch((e) => {
        console.error(e);
        runBanner();
      });
  }

// Banner animation effect
function runBanner() {
  const nextDelay = 14000;
  const transDuration = 10000;
  // Switch item every interval and
  setInterval(() => {
    const prev = banner.visibleId;
    banner.visibleId = banner.visibleId === 3 ? 1 : banner.visibleId + 1;
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
  }, nextDelay);

  // Observe banner and set is visible or not to
  // Update float button and menu position
  let options = {
    root: null,
    rootMargin: "0px",
    threshold: 0.35,
  };

  let observer = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) bannerStore.setBannerVisible(true);
      if (!entry.isIntersecting) bannerStore.setBannerVisible(false);
    });
  }, options);

  observer.observe(document.getElementById("banner"));
}

onMounted(() => {
  setupBanner();
});
</script>

<template>
  <div id="banner" tabindex="-1" role="list" class="banner-container">
    <div role="img" aria-hidden="true" class="banner-bg"></div>
    <div
      v-for="(bannerEl, index) in banner.default"
      role="listitem"
      :id="`banner-item-${index}`"
      class="banner-item"
      :class="[index === 1 ? 'left-0' : 'left-full opacity-0']"
    >
      <p class="banner-item-text">
        {{  bannerEl.title }}
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
      <div
        v-html="bannerEl.content"></div>
    </div>
  </div>
</template>
