<script setup>
import { reactive, onMounted, computed } from "vue";

/**
 * @name Dashboard/Header.vue
 * @description This component is a header displaying the current page endpoint.
 */

const header = reactive({
  splitPath: [],
  currPath: computed(() => {
    if (header.splitPath.length === 0) return "page";
    return header.splitPath[header.splitPath.length - 1].replaceAll(" ", "_");
  }),
  lastPath: computed(() => {
    if (header.splitPath.length === 0) return "page";
    return header.splitPath[header.splitPath.length - 1].replaceAll(" ", "_");
  }),
});

onMounted(() => {
  // Get current route and try to match with a menu item to highlight
  const pathName = window.location.pathname.toLowerCase();
  // Remove queries
  let splitPath = pathName.split("?")[0].split("/");
  if (splitPath.length === 0) return (header.splitPath = []);
  // Remove .html and index
  for (let i = 0; i < splitPath.length; i++) {
    const el = splitPath[i];
    splitPath[i] = el.replace(".html", "").replace("-", " ");
  }
  if (splitPath[splitPath.length - 1].includes("index")) splitPath.pop();
  splitPath = splitPath.filter((item) => item !== "");
  // We want to keep only last 2 params to avoid wide path
  for (let i = 0; splitPath.length > 2; i++) {
    splitPath.shift();
  }

  header.splitPath = splitPath;
});
</script>

<template>
  <div class="header-container">
    <header class="header-el">
      <div class="header-wrap">
        <nav>
          <!-- breadcrumb -->
          <h2 class="header-title">
            {{
              $t(
                `dashboard_${header.currPath}`,
                $t(
                  "dashboard_placeholder",
                  $t("dashboard_placeholder", header.currPath)
                )
              )
            }}
          </h2>
          <ul class="header-breadcrumb-container">
            <li class="header-breadcrumb-item first">
              {{ $t("dashboard_bw") }}
            </li>
            <li class="header-breadcrumb-item slash mobile active">
              {{
                $t(
                  `dashboard_${header.lastPath}`,
                  $t(
                    "dashboard_placeholder",
                    $t("dashboard_placeholder", header.lastPath)
                  )
                )
              }}
            </li>
          </ul>
        </nav>
      </div>
    </header>
  </div>
</template>
