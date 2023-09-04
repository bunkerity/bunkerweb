<script setup>
// Components
import Footer from "@components/Footer.vue";
import Loader from "@components/Loader.vue";
import Menu from "@components/Menu.vue";
import FeedbackStructure from "@components/Feedback/Structure.vue";
import News from "@components/News.vue";
import Header from "@components/Header.vue";
</script>

<template>
  <noscript class="no-script"
    >Your browser does not support JavaScript!</noscript
  >
  <Loader />
  <Menu />
  <FeedbackStructure />
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
