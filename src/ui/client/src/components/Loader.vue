<script setup>
import { onMounted } from "vue";

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

      setTimeout(() => {
        this.logoContainer.remove();
      }, 1800);
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
  <div role="group" data-loader class="loader-container">
    <p class="sr-only">{{ $t("dashboard_loader_label") }}</p>
    <img
      data-loader-img
      src="/images/logo-menu-2.png"
      class="loader-container-img"
      :alt="$t('dashboard_loader_alt_logo')"
    />
  </div>
</template>
