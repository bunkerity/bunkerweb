<script setup>
import { onMounted, reactive } from "vue";
import { footerIndex } from "@utils/tabindex";
import { useI18n } from "vue-i18n";
const { t } = useI18n();

/**
 *@name Dashboard/Footer.vue
 * @description This component is a footer that display essential links.
 * You have all the links to the main website, the documentation, the privacy policy, the blog, the license and the sitemap.
 */

const items = [
  {
    href: "https://www.bunkerweb.io?utm_campaign=self&utm_source=ui",
    title: t("dashboard_bw"),
  },
  {
    href: "https://docs.bunkerweb.io?utm_campaign=self&utm_source=ui",
    title: t("dashboard_docs"),
  },
  {
    href: "https://www.bunkerweb.io/privacy-policy?utm_campaign=self&utm_source=ui",
    title: t("dashboard_privacy"),
  },
  {
    href: "https://www.bunkerity.com/fr/blog?utm_campaign=self&utm_source=ui",
    title: t("dashboard_blog"),
  },
  {
    href: "https://github.com/bunkerity/bunkerweb/blob/master/LICENSE",
    title: t("dashboard_license"),
  },
  {
    href: "/sitemap",
    title: t("dashboard_sitemap"),
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
            <a
              :tabindex="footerIndex"
              :href="item.href"
              class="footer-list-item"
              target="_blank"
            >
              {{ item.title }}
            </a>
          </li>
        </ul>
      </div>
    </div>
  </footer>
</template>
