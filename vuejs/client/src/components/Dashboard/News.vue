<script setup>
import { onMounted, reactive } from "vue";
import { newsIndex } from "@utils/tabindex.js";
import { useBannerStore } from "@store/global.js";
// Use to update position when banner is visible or not
const bannerStore = useBannerStore();

// DATA
const news = reactive({
  isActive: false,
  posts: [],
});

onMounted(() => {
  try {
    fetch("https://www.bunkerweb.io/api/posts/0/2")
      .then((res) => {
        return res.json();
      })
      .then((res) => {
        news.posts = res.data;
      });
  } catch (err) {}
});
</script>

<template>
  <!-- float button-->
  <button
    :tabindex="newsIndex"
    aria-controls="sidebar-news"
    :aria-expanded="news.isActive ? 'true' : 'false'"
    @click="news.isActive = news.isActive ? false : true"
    :class="['news-float-btn', bannerStore.bannerClass]"
    class="news-float-btn"
    aria-describedby="sidebar-news-toggle"
  >
    <span class="sr-only" id="sidebar-news-toggle">
      {{ $t("dashboard_news_toggle_sidebar") }}
    </span>
    <svg
      role="img"
      aria-hidden="true"
      class="news-float-btn-svg"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 512 512"
    >
      <path
        d="M96 96c0-35.3 28.7-64 64-64H448c35.3 0 64 28.7 64 64V416c0 35.3-28.7 64-64 64H80c-44.2 0-80-35.8-80-80V128c0-17.7 14.3-32 32-32s32 14.3 32 32V400c0 8.8 7.2 16 16 16s16-7.2 16-16V96zm64 24v80c0 13.3 10.7 24 24 24H424c13.3 0 24-10.7 24-24V120c0-13.3-10.7-24-24-24H184c-13.3 0-24 10.7-24 24zm0 184c0 8.8 7.2 16 16 16h96c8.8 0 16-7.2 16-16s-7.2-16-16-16H176c-8.8 0-16 7.2-16 16zm160 0c0 8.8 7.2 16 16 16h96c8.8 0 16-7.2 16-16s-7.2-16-16-16H336c-8.8 0-16 7.2-16 16zM160 400c0 8.8 7.2 16 16 16h96c8.8 0 16-7.2 16-16s-7.2-16-16-16H176c-8.8 0-16 7.2-16 16zm160 0c0 8.8 7.2 16 16 16h96c8.8 0 16-7.2 16-16s-7.2-16-16-16H336c-8.8 0-16 7.2-16 16z"
      />
    </svg>
  </button>
  <!-- end float button-->

  <!-- right sidebar -->
  <aside
    :aria-hidden="news.isActive ? 'false' : 'true'"
    id="sidebar-news"
    :class="[news.isActive ? '' : 'translate-x-[22.5rem]', 'news-sidebar']"
  >
    <!-- close btn-->
    <button
      :tabindex="news.isActive ? newsIndex : '-1'"
      class="news-close-btn"
      aria-controls="sidebar-news"
      :aria-expanded="news.isActive ? 'true' : 'false'"
      @click="news.isActive = false"
      aria-describedby="sidebar-news-close"
    >
      <span class="sr-only" id="sidebar-news-close">
        {{ $t("dashboard_news_close_sidebar") }}
      </span>
      <svg
        role="img"
        aria-hidden="true"
        @click="news.isActive = false"
        class="news-close-btn-svg"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 320 512"
      >
        <path
          d="M310.6 150.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L160 210.7 54.6 105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L114.7 256 9.4 361.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 301.3 265.4 406.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L205.3 256 310.6 150.6z"
        />
      </svg>
    </button>
    <!-- close btn-->

    <!-- header -->
    <div class="news-sidebar-header">
      <div class="float-left">
        <h5 class="news-sidebar-title">{{ $t("dashboard_news_title") }}</h5>
        <p class="news-sidebar-subtitle">{{ $t("dashboard_news_subtitle") }}</p>
      </div>
    </div>
    <hr class="line-separator" />
    <!-- end header -->
    {{ news.posts }}
    <!-- news-->
    <div class="flex-auto overflow-auto">
      <p v-if="news.posts.length === 0" class="news-sidebar-no-posts-content">
        {{ $t("dashboard_news_fetch_error") }}
      </p>
    </div>
    <!-- end news-->

    <!-- newsletter -->
    <hr class="line-separator" />

    <form
      action="https://bunkerity.us1.list-manage.com/subscribe/post?u=ec5b1577cf427972b9bd491a6&amp;id=37076d9d67"
      method="POST"
      class="news-newsletter-form"
      id="subscribe-newsletter"
    >
      <h5 class="news-newsletter-title">
        {{ $t("dashboard_newsletter_title") }}
      </h5>
      <div class="flex">
        <input
          :tabindex="news.isActive ? newsIndex : '-1'"
          type="text"
          id="newsletter-email"
          name="EMAIL"
          class="news-newsletter-input"
          :placeholder="$t('dashboard_newsletter_placeholder')"
          pattern="[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}$"
          required
        />
      </div>
      <div class="flex mt-2 mb-4">
        <div class="relative">
          <div
            data-checkbox-handler="newsletter-check"
            class="relative mb-7 md:mb-0"
          >
            <input
              :tabindex="news.isActive ? newsIndex : '-1'"
              id="newsletter-check"
              class="news-newsletter-checkbox"
              type="checkbox"
              data-pattern="^(yes|no)$"
              value="no"
              required
            />
            <svg
              role="img"
              aria-hidden="true"
              data-checkbox-handler="newsletter-check"
              class="news-newsletter-checkbox-svg"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 512 512"
            >
              <path
                d="M470.6 105.4c12.5 12.5 12.5 32.8 0 45.3l-256 256c-12.5 12.5-32.8 12.5-45.3 0l-128-128c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0L192 338.7 425.4 105.4c12.5-12.5 32.8-12.5 45.3 0z"
              ></path>
            </svg>
          </div>
        </div>
        <label class="news-newsletter-checkbox-content" for="newsletter-check">
          {{ $t("dashboard_newsletter_privacy_text") }}
          <a
            :tabindex="news.isActive ? newsIndex : '-1'"
            class="italic"
            href="https://www.bunkerity.com/privacy-policy?utm_campaign=self&utm_source=ui"
            target="_blank"
          >
            {{ $t("dashboard_newsletter_privacy_text_link") }}
          </a>
        </label>
      </div>
      <button
        :tabindex="news.isActive ? newsIndex : '-1'"
        type="submit"
        formtarget="_blank"
        class="news-newsletter-confirm-btn"
      >
        {{ $t("dashboard_newsletter_subscribe_button") }}
      </button>
    </form>
    <!-- end newsletter -->
  </aside>
  <!-- end right sidebar -->
</template>
