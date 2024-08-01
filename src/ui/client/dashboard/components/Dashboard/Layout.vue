<script setup>
// Components
import Footer from "@components/Dashboard/Footer.vue";
import Loader from "@components/Dashboard/Loader.vue";
import LangSwitch from "@components/Dashboard/LangSwitch.vue";
import Menu from "@components/Dashboard/Menu.vue";
import News from "@components/Dashboard/News.vue";
import Header from "@components/Dashboard/Header.vue";
import Banner from "@components/Dashboard/Banner.vue";
import Feedback from "@components/Dashboard/Feedback.vue";

/**
 *@name Dashboard/Layout.vue
 * @description This component is a layout that wraps the main content of the dashboard.
 * It includes the header, the menu, the news, the language switcher, the loader, the banner and the footer.
 * The content part is a slot that can be filled with custom components or using the Builder.vue.
 */
</script>

<template>
  <noscript class="no-script">
    Your browser does not support JavaScript!
  </noscript>
  <Loader />
  <LangSwitch />
  <Banner />
  <Menu />
  <Feedback />
  <News />
  <Header />
  <!-- info -->
  <main class="content-container">
    <div class="content-wrap">
      <slot></slot>
    </div>
    <Footer />
  </main>
  <!-- end info -->
</template>
