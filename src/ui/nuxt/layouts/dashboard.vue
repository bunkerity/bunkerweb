<script setup>
useHead({
  bodyAttrs: {
    class: "bg-primary overflow-x-hidden overflow-y-auto",
  },
});
useGlobal();
</script>

<template>
  <noscript class="no-script"
    >Your browser does not support JavaScript!</noscript
  >
  <Loader />
  <Menu />
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
