<script setup>
import { onMounted, reactive, ref } from "vue";
import logoMenu2 from "@public/images/logo-menu-2.png";

/**
  @name Dashboard/Loader.vue
  @description This component is a loader used to transition between pages.
*/

const loader = reactive({
  isActive: true,
});

const logo = ref();
const logoContainer = ref();

function loading() {
  // delay before stopping the loading
  setTimeout(() => {
    logoContainer.value.classList.add("opacity-0");
  }, 750);

  setTimeout(() => {
    loader.isActive = false;
    logoContainer.value.classList.add("hidden");
  }, 1050);
  // loading logic

  if (!loader.isActive) return;
  setTimeout(() => {
    logo.value.classList.toggle("scale-105");
    loading();
  }, 300);
}

onMounted(() => {
  loading();
});
</script>

<template>
  <div
    ref="logoContainer"
    role="progressbar"
    aria-labelledby="loader-text"
    data-loader
    class="loader-container"
    :aria-hidden="loader.isActive ? 'false' : 'true'"
  >
    <p id="loader-text" class="sr-only">{{ $t("dashboard_loading") }}</p>
    <img
      ref="logo"
      aria-hidden="true"
      :src="logoMenu2"
      class="loader-container-img"
      :alt="$t('dashboard_logo_alt')"
    />
  </div>
</template>
