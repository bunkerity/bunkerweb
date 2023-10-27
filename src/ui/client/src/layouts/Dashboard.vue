<script setup>
// Components
import Footer from "@components/Footer.vue";
import Loader from "@components/Loader.vue";
import Menu from "@components/Menu.vue";
import FeedbackStructure from "@components/Feedback/Structure.vue";
import News from "@components/News.vue";
import Header from "@components/Header.vue";
import Logs from "@components/Logs.vue";
import Refresh from "@components/Refresh.vue";
</script>

<template>
  <noscript class="no-script"
    >Your browser does not support JavaScript!</noscript
  >
  <Loader />

  <!-- info -->
  <main class="content-container">
    <Menu />
    <FeedbackStructure />
    <News />
    <Logs />
    <Refresh />
    <div class="content-wrap">
      <Header />
      <slot></slot>
    </div>
    <Footer />
  </main>
  <!-- end info -->
</template>
