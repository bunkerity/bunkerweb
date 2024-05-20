<script setup>
// Components
import Footer from "@components/Footer.vue";
import Loader from "@components/Loader.vue";
import LangSwitch from "@components/LangSwitch.vue";
import Menu from "@components/Menu.vue";
import FeedbackStructure from "@components/Feedback/Structure.vue";
import News from "@components/News.vue";
import Header from "@components/Header.vue";
import Refresh from "@components/Refresh.vue";
import Banner from "@components/Banner.vue";
</script>

<template>
  <noscript class="no-script"
    >Your browser does not support JavaScript!</noscript
  >
  <Loader />
  <LangSwitch />
  <Banner />
  <!-- info -->
  <main role="main" class="content-container">
    <Menu />
    <News />
    <div class="content-wrap">
      <Header />
      <slot></slot>
    </div>
    <Footer />
  </main>
  <!-- end info -->
</template>
