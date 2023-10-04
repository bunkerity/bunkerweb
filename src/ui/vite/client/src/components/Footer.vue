<script setup>
import { onMounted, reactive } from "vue";
const items = [
  { href: "https://www.bunkerweb.io", title: "Bunkerweb" },
  { href: "https://docs.bunkerweb.io", title: "Docs" },
  { href: "https://www.bunkerweb.io/privacy-policy", title: "Privacy" },
  { href: "https://www.bunkerity.com/fr/blog/", title: "Blog" },
  {
    href: "https://github.com/bunkerity/bunkerweb/blob/master/LICENSE",
    title: "License",
  },
];

const footer = reactive({
  date: "",
});

onMounted(() => {
  footer.date = `Copyright © ${new Date().getFullYear()} Bunkerity`;
});
</script>

<template>
  <footer class="footer-container">
    <div class="footer-wrap">
      <div class="footer-items-container">
        <div class="footer-item-right-container">
          <div class="footer-item-right">
            {{ footer.date }}
          </div>
        </div>
        <ul class="footer-list-container">
          <li v-for="item in items">
            <a :href="item.href" class="footer-list-item" target="_blank">{{
              item.title
            }}</a>
          </li>
        </ul>
      </div>
    </div>
  </footer>
</template>
