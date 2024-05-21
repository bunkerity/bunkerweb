<script setup>
// Components
import Footer from "@components/dashboard/Footer.vue";
import Loader from "@components/dashboard/Loader.vue";
import LangSwitch from "@components/dashboard/LangSwitch.vue";
import Menu from "@components/dashboard/Menu.vue";
import News from "@components/dashboard/News.vue";
import Header from "@components/dashboard/Header.vue";
import Banner from "@components/dashboard/Banner.vue";

/** 
  @name Dashboard/Layout.vue
  @description This component is a layout that wraps the main content of the dashboard.
  It includes the header, the menu, the news, the language switcher, the loader, the banner and the footer.
  The content part is a slot that can be filled with custom components or using the Builder.vue.
*/
</script>

<template>
  <noscript class="no-script"
    >Your browser does not support JavaScript!</noscript
  >
  <Loader />
  <LangSwitch />
  <Banner />
  <Menu />
  <News />
  <Header />
  <!-- info -->
  <main role="main" class="content-container">
    <div class="content-wrap">
      <slot></slot>
    </div>
    <Footer />
  </main>
  <!-- end info -->
</template>
