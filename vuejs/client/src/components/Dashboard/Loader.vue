<script setup>
import { onMounted } from "vue";
import logoMenu2 from "@public/images/logo-menu-2.png";

/** 
  @name Dashboard/Loader.vue
  @description This component is a loader used to transition between pages.
*/

onMounted(() => {
  class Loader {
    constructor() {
      this.logoContainer = document.querySelector("[data-loader]");
      this.logoEl = document.querySelector("[data-loader-img]");
      this.isLoading = true;
      this.init();
    }

    init() {
      this.loading();
      setTimeout(() => {
        this.logoContainer.classList.add("opacity-0");
      }, 1350);

      setTimeout(() => {
        this.isLoading = false;
        this.logoContainer.classList.add("hidden");
      }, 1650);
    }

    loading() {
      if ((this.isLoading = true)) {
        setTimeout(() => {
          this.logoEl.classList.toggle("scale-105");
          this.loading();
        }, 300);
      }
    }
  }

  const setLoader = new Loader();
});
</script>

<template>
  <div
    role="progressbar"
    aria-labelledby="loader-text"
    data-loader
    class="loader-container"
  >
    <p id="loader-text" class="sr-only">{{ $t("dashboard_loading") }}</p>
    <img
      role="img"
      aria-hidden="true"
      data-loader-img
      :src="logoMenu2"
      class="loader-container-img"
      :alt="$t('dashboard_logo_alt')"
    />
  </div>
</template>
