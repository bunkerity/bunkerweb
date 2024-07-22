<script setup>
import Icons from "@components/Widget/Icons.vue";
import { reactive, onBeforeMount } from "vue";
import { menuIndex, menuFloatIndex } from "@/utils/tabindex.js";
import { useBannerStore } from "@store/global.js";

// Get assets path
import logo from "@assets/img/logo-menu.png";
import logo2 from "@assets/img/logo-menu-2.png";
// Change path on PROD removing '/' in order to get the right path
const logoMenu = logo.substring(import.meta.env.DEV ? 0 : 1);
const logoMenu2 = logo2.substring(import.meta.env.DEV ? 0 : 1);

/** 
  @name Dashboard/Menu.vue
  @description This component is a menu that display essential links.
  You have all the links to the main pages, the plugins pages, the social links and the logout button.
*/

// Use to update position when banner is visible or not
const bannerStore = useBannerStore();

// Navigation with components
// resolveComponent allow to replace a tag by a real Vue component
const navList = [
  { tag: "home", svg: "house", svgColor: "cyan", path: "home" },
  {
    tag: "instances",
    svg: "box",
    svgColor: "dark",
    path: "instances",
  },

  {
    tag: "global_config",
    svg: "settings",
    svgColor: "blue",
    path: "global-config",
  },
  {
    tag: "services",
    svg: "disk",
    svgColor: "orange",
    path: "services",
  },
  {
    tag: "configs",
    svg: "gear",
    svgColor: "purple",
    path: "configs",
  },
  {
    tag: "plugins",
    svg: "puzzle",
    svgColor: "yellow",
    path: "plugins",
  },
  {
    tag: "cache",
    svg: "carton",
    svgColor: "purple",
    path: "cache",
  },
  {
    tag: "reports",
    svg: "flag",
    svgColor: "amber",
    path: "reports",
  },
  { tag: "bans", svg: "funnel", svgColor: "red", path: "bans" },
  { tag: "jobs", svg: "task", svgColor: "emerald", path: "jobs" },
  { tag: "logs", svg: "list", svgColor: "dark", path: "logs" },
];

// Social links
const socialList = [
  {
    tag: "twitter",
    href: "https://twitter.com/bunkerity",
    svg: "twitter",
    svgColor: "twitter",
  },
  {
    tag: "linkedin",
    href: "https://www.linkedin.com/company/bunkerity/",
    svg: "linkedin",
    svgColor: "linkedin",
  },
  {
    tag: "discord",
    href: "https://discord.gg/fTf46FmtyD",
    svg: "discord",
    svgColor: "discord",
  },
  {
    tag: "github",
    href: "https://github.com/bunkerity",
    svg: "github",
    svgColor: "github",
  },
];

const menu = reactive({
  pagePlugins: [], // Render custom page plugins links
  darkMode: false, // Apply dark mode state
  isActive: false, // Handle menu display/expand
  isDesktop: true, // Expand logic exclude with desktop
  currPath: false,
  username: "",
});

function getDarkMode() {
  let darkMode = false;
  // Case on storage
  if (sessionStorage.getItem("mode")) {
    darkMode = sessionStorage.getItem("mode") === "dark" ? true : false;
  } else if (
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches
  ) {
    // dark mode
    darkMode = true;
    sessionStorage.setItem("mode", "dark");
  } else {
    darkMode = false;
    sessionStorage.setItem("mode", "light");
  }

  return darkMode;
}

function switchMode() {
  menu.darkMode = menu.darkMode ? false : true;
  sessionStorage.setItem("mode", menu.darkMode ? "dark" : "light");
  updateMode();
}

function updateMode() {
  try {
    menu.darkMode
      ? document.querySelector("html").classList.add("dark")
      : document.querySelector("html").classList.remove("dark");
  } catch (err) {}
}

function closeMenu() {
  menu.isActive = false;
}

function toggleMenu() {
  menu.isActive = menu.isActive ? false : true;
}

// Check device desktop using breakpoint
onBeforeMount(() => {
  // setup darkmode
  menu.darkMode = getDarkMode();
  updateMode();
  // Get current route and try to match with a menu item to highlight
  const pathName = window.location.pathname.toLowerCase();
  navList.forEach((item) => {
    const title = item.tag.replaceAll(" ", "-").toLowerCase();
    if (pathName.includes(title)) menu.currPath = title;
  });

  // Determine menu behavior (static or float)
  menu.isDesktop = window.innerWidth < 1200 ? false : true;
  window.addEventListener("resize", () => {
    menu.isDesktop = window.innerWidth < 1200 ? false : true;
  });

  // Get username
  const dataAtt = "data-server-global";
  const dataEl = document.querySelector(`[${dataAtt}]`);
  const data =
    dataEl && !dataEl.getAttribute(dataAtt).includes(dataAtt)
      ? JSON.parse(dataEl.getAttribute(dataAtt))
      : {};
  menu.username = data?.username || "";
});
</script>

<template>
  <!-- float button-->
  <button
    aria-controls="sidebar-menu"
    :tabindex="menu.isDesktop ? '-1' : menuFloatIndex"
    :aria-expanded="menu.isDesktop ? 'true' : menu.isActive ? 'true' : 'false'"
    @click="toggleMenu()"
    :class="['menu-float-btn', bannerStore.bannerClass]"
    :aria-labelledby="'float-btn-sidebar'"
  >
    <span id="float-btn-sidebar" class="sr-only">
      {{ $t("dashboard_menu_toggle_sidebar") }}
    </span>
    <svg
      role="img"
      aria-hidden="true"
      fill="#0D6EFD"
      class="menu-float-btn-svg"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 512 512"
    >
      <path
        d="M0 96C0 78.3 14.3 64 32 64H416c17.7 0 32 14.3 32 32s-14.3 32-32 32H32C14.3 128 0 113.7 0 96zM0 256c0-17.7 14.3-32 32-32H416c17.7 0 32 14.3 32 32s-14.3 32-32 32H32c-17.7 0-32-14.3-32-32zM448 416c0 17.7-14.3 32-32 32H32c-17.7 0-32-14.3-32-32s14.3-32 32-32H416c17.7 0 32 14.3 32 32z"
      />
    </svg>
  </button>
  <!-- end float button-->

  <!-- left sidebar  -->
  <aside
    data-is="menu"
    id="sidebar-menu"
    data-sidebar-menu
    :aria-hidden="menu.isDesktop ? 'false' : menu.isActive ? 'false' : 'true'"
    :class="[
      'menu-container',
      bannerStore.bannerClass,
      menu.isDesktop ? 'active' : menu.isActive ? 'active' : 'inactive',
    ]"
  >
    <!-- close btn-->
    <button
      aria-controls="sidebar-menu"
      :aria-expanded="
        menu.isDesktop ? 'true' : menu.isActive ? 'true' : 'false'
      "
      :tabindex="menu.isDesktop ? menuIndex : menu.isActive ? menuIndex : '-1'"
      @click="closeMenu()"
      class="menu-close-btn"
      :class="[menu.isDesktop ? 'hidden' : '']"
      :aria-labelledby="'float-btn-close-menu'"
    >
      <span id="float-btn-close-menu" class="sr-only">
        {{ $t("dashboard_menu_close_sidebar") }}
      </span>
      <svg
        role="img"
        aria-hidden="true"
        @click="closeMenu()"
        class="menu-close-btn-svg"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 320 512"
      >
        <path
          d="M310.6 150.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L160 210.7 54.6 105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L114.7 256 9.4 361.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 301.3 265.4 406.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L205.3 256 310.6 150.6z"
        />
      </svg>
    </button>
    <!-- close btn-->

    <div class="menu-top-content">
      <!-- logo and version -->
      <div class="menu-logo-container">
        <a
          :tabindex="
            menu.isDesktop ? menuIndex : menu.isActive ? menuIndex : '-1'
          "
          aria-labelledby="logo-link-label"
          class="menu-logo-link-container"
          :href="menu.currPath === '/home' ? '#' : '/home'"
        >
          <span id="logo-link-label" class="sr-only">
            {{ $t("dashboard_logo_link_label") }}
          </span>
          <img
            :aria-hidden="'true'"
            v-if="menu.darkMode"
            :src="logoMenu2"
            :alt="$t('dashboard_logo_alt')"
            class="menu-logo-dark"
          />
          <img
            :aria-hidden="'true'"
            v-if="!menu.darkMode"
            :src="logoMenu"
            :alt="$t('dashboard_logo_alt')"
            class="menu-logo-light"
          />
        </a>
      </div>
      <div class="menu-account-title-container">
        <p class="menu-account-title">
          {{ menu.username.substring(0, 16) }}
        </p>
        <a
          :tabindex="
            menu.isDesktop ? menuIndex : menu.isActive ? menuIndex : '-1'
          "
          class="menu-account-link"
          href="/account"
          >{{ $t("dashboard_manage_account") }}</a
        >
      </div>
      <hr class="menu-separator" />
      <!-- end logo version -->
    </div>

    <nav :class="['menu-nav-list-container', bannerStore.bannerClass]">
      <ul class="menu-nav-list">
        <!-- item -->
        <li v-for="(item, id) in navList" :key="id" class="menu-nav-list-item">
          <a
            :tabindex="
              menu.isDesktop ? menuIndex : menu.isActive ? menuIndex : '-1'
            "
            :class="[
              item.path.toLowerCase().includes(menu.currPath) ? 'active' : '',
              'menu-nav-item-anchor',
            ]"
            :href="
              item.path.toLowerCase().includes(menu.currPath) ? '#' : item.path
            "
          >
            <div class="menu-nav-item-container">
              <Icons :iconName="item.svg" />
            </div>
            <span class="menu-nav-item-title">
              {{ $t(`dashboard_${item.tag}`) }}
            </span>
          </a>
        </li>
        <!-- end item -->
      </ul>
      <!-- end default anchor -->

      <!-- plugins -->
      <ul v-if="menu.pagePlugins.length">
        <li class="menu-page-plugin-item-title">
          <p class="menu-page-plugin-title">
            {{ $t("dashboard_menu_plugins_title") }}
          </p>
        </li>
        <li
          v-for="plugin in menu.pagePlugins"
          class="menu-page-plugin-item-page"
        >
          <a
            :tabindex="
              menu.isDesktop ? menuIndex : menu.isActive ? menuIndex : '-1'
            "
            target="_blank"
            class="menu-page-plugin-anchor"
            :href="`/plugins?plugin_id=${plugin.id}`"
          >
            <div aria-hidden="true" class="menu-page-plugin-svg-container">
              <Icons
                :iconName="plugin.type === 'pro' ? 'crown' : 'free'"
                :color="plugin.type === 'pro' ? 'amber' : 'dark'"
              />
            </div>
            <span class="menu-page-plugin-name">{{ plugin.name }}</span>
          </a>
        </li>
      </ul>
      <!-- end plugins -->
    </nav>

    <!-- bottom sidebar  -->
    <div class="menu-bottom-content">
      <hr class="line-separator" />

      <!-- dark/light mode -->
      <div class="menu-mode-container">
        <input
          :tabindex="
            menu.isDesktop ? menuIndex : menu.isActive ? menuIndex : '-1'
          "
          :checked="menu.darkMode"
          @click="switchMode()"
          @keyup.enter="switchMode()"
          id="darkMode"
          data-dark-toggle
          class="menu-mode-checkbox"
          type="checkbox"
        />
        <label for="darkMode" data-dark-toggle-label class="menu-mode-label">
          {{
            menu.darkMode
              ? $t("dashboard_menu_mode_dark")
              : $t("dashboard_menu_mode_light")
          }}
        </label>
      </div>
      <!-- end dark/light mode -->

      <!-- social-->
      <ul data-is="social" class="menu-social-list">
        <li v-for="(item, id) in socialList" class="menu-social-list-item">
          <span :id="`menu-social-item-${id}`" class="sr-only">
            {{ $t(`dashboard_menu_${item.tag}_label`) }}
          </span>
          <a
            :tabindex="
              menu.isDesktop ? menuIndex : menu.isActive ? menuIndex : '-1'
            "
            :href="item.href"
            target="_blank"
            :aria-labelledby="`menu-social-item-${id}`"
          >
            <Icons :iconName="item.svg" :color="item.svgColor" />
          </a>
        </li>
      </ul>
      <!-- end social-->

      <!-- logout-->
      <div class="menu-logout-content">
        <button
          :tabindex="
            menu.isDesktop ? menuIndex : menu.isActive ? menuIndex : '-1'
          "
          @click="getlogout()"
          class="menu-logout"
        >
          {{ $t("dashboard_menu_log_out") }}
        </button>
      </div>
      <!-- end logout-->
    </div>
    <!-- end bottom sidebar  -->
  </aside>
  <!-- end left sidebar -->
</template>
