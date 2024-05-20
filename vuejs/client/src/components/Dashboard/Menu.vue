<script setup>
import MenuSvgHome from "@components/Menu/Svg/Home.vue";
import MenuSvgInstances from "@components/Menu/Svg/Instances.vue";
import MenuSvgGlobalConf from "@components/Menu/Svg/GlobalConf.vue";
import MenuSvgConfigs from "@components/Menu/Svg/Configs.vue";
import MenuSvgPlugins from "@components/Menu/Svg/Plugins.vue";
import MenuSvgJobs from "@components/Menu/Svg/Jobs.vue";
import MenuSvgTwitter from "@components/Menu/Svg/Twitter.vue";
import MenuSvgLinkedin from "@components/Menu/Svg/Linkedin.vue";
import MenuSvgDiscord from "@components/Menu/Svg/Discord.vue";
import MenuSvgServices from "@components/Menu/Svg/Services.vue";
import MenuSvgGithub from "@components/Menu/Svg/Github.vue";
import MenuSvgBans from "@components/Menu/Svg/Bans.vue";
import MenuSvgActions from "@components/Menu/Svg/Actions.vue";
import MenuSvgReporting from "@components/Menu/Svg/Reporting.vue";
import { reactive, onMounted } from "vue";
import { menuIndex, menuFloatIndex } from "@/utils/tabindex.js";
import { useBannerStore } from "@store/global.js";
import logoMenu2 from "@public/images/logo-menu-2.png";
import logoMenu from "@public/images/logo-menu.png";

// Use to update position when banner is visible or not
const bannerStore = useBannerStore();

// Navigation with components
// resolveComponent allow to replace a tag by a real Vue component
const navList = [
  { tag: "home", svg: MenuSvgHome, path: "/home" },
  {
    tag: "instances",
    svg: MenuSvgInstances,
    path: "/instances",
  },

  {
    tag: "global_config",
    svg: MenuSvgGlobalConf,
    path: "/global-config",
  },
  {
    tag: "services",
    svg: MenuSvgServices,
    path: "/services",
  },
  {
    tag: "configs",
    svg: MenuSvgConfigs,
    path: "/configs",
  },
  {
    tag: "plugins",
    svg: MenuSvgPlugins,
    path: "/plugins",
  },
  { tag: "jobs", svg: MenuSvgJobs, path: "/jobs" },
  { tag: "bans", svg: MenuSvgBans, path: "/bans" },
  {
    tag: "actions",
    svg: MenuSvgActions,
    path: "/actions",
  },
  {
    tag: "reporting",
    svg: MenuSvgReporting,
    path: "/reporting",
  },
];

// Social links
const socialList = [
  {
    tag: "twitter",
    href: "https://twitter.com/bunkerity",
    svg: MenuSvgTwitter,
  },
  {
    tag: "linkedin",
    href: "https://www.linkedin.com/company/bunkerity/",
    svg: MenuSvgLinkedin,
  },
  {
    tag: "discord",
    href: "https://discord.gg/fTf46FmtyD",
    svg: MenuSvgDiscord,
  },
  {
    tag: "github",
    href: "https://github.com/bunkerity",
    svg: MenuSvgGithub,
  },
];

const menu = reactive({
  pagePlugins: [], // Render custom page plugins links
  darkMode: false, // Apply dark mode state
  isActive: false, // Handle menu display/expand
  isDesktop: true, // Expand logic exclude with desktop
  currPath: false,
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
onMounted(() => {
  // setup darkmode
  menu.darkMode = getDarkMode();

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
    aria-describedby="sidebar-menu-toggle"
  >
    <span class="sr-only" id="sidebar-menu-toggle">
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
    id="sidebar-menu"
    data-sidebar-menu
    :aria-hidden="menu.isDesktop ? 'false' : menu.isActive ? 'false' : 'true'"
    :class="[
      'menu-container xl:translate-x-0',
      bannerStore.bannerClass,
      menu.isDesktop ? true : menu.isActive ? '' : 'active',
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
      aria-describedby="sidebar-menu-close"
    >
      <span class="sr-only" id="sidebar-menu-close">
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
      <div class="w-full">
        <a
          :tabindex="
            menu.isDesktop ? menuIndex : menu.isActive ? menuIndex : '-1'
          "
          aria-labelledby="logo-link-label"
          class="menu-logo-container"
          :href="menu.currPath === '/home' ? '#' : '/home'"
        >
          <span id="logo-link-label" class="sr-only">
            {{ $t("dashboard_logo_link_label") }}
          </span>
          <img :aria-hidden="'true'" :src="logoMenu2" class="menu-logo-dark" />
          <img :aria-hidden="'true'" :src="logoMenu" class="menu-logo-light" />
        </a>
      </div>
      <div class="mt-2 w-full px-1">
        <h1 class="menu-account-title">
          {{ username.substring(0, 10) }}
        </h1>
        <a class="menu-account-link" href="/account">manage account </a>
      </div>
      <hr class="menu-separator" />
      <!-- end logo version -->
    </div>

    <div :class="[menu - nav - list - container, bannerStore.bannerClass]">
      <ul role="navigation" class="menu-nav-list">
        <!-- item -->
        <li v-for="(item, id) in navList" :key="id" class="mt-0.5 w-full">
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
              <component :is="item.svg"></component>
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
      <ul>
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
              <svg
                v-if="plugin.type !== 'pro'"
                role="img"
                aria-hidden="true"
                class="fill-gray-500 h-5 w-5 relative"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 384 512"
              >
                <path
                  d="M0 64C0 28.7 28.7 0 64 0H224V128c0 17.7 14.3 32 32 32H384V448c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V64zm384 64H256V0L384 128z"
                />
              </svg>
              <svg
                v-if="plugin.type === 'pro'"
                class="h-5 w-5 dark:brightness-90 relative"
                viewBox="0 0 48 46"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  class="fill-yellow-500"
                  d="M43.218 28.2327L43.6765 23.971C43.921 21.6973 44.0825 20.1957 43.9557 19.2497L44 19.25C46.071 19.25 47.75 17.5711 47.75 15.5C47.75 13.4289 46.071 11.75 44 11.75C41.929 11.75 40.25 13.4289 40.25 15.5C40.25 16.4366 40.5935 17.2931 41.1613 17.9503C40.346 18.4535 39.2805 19.515 37.6763 21.1128C36.4405 22.3438 35.8225 22.9593 35.1333 23.0548C34.7513 23.1075 34.3622 23.0532 34.0095 22.898C33.373 22.6175 32.9485 21.8567 32.0997 20.335L27.6262 12.3135C27.1025 11.3747 26.6642 10.5889 26.2692 9.95662C27.89 9.12967 29 7.44445 29 5.5C29 2.73857 26.7615 0.5 24 0.5C21.2385 0.5 19 2.73857 19 5.5C19 7.44445 20.11 9.12967 21.7308 9.95662C21.3358 10.589 20.8975 11.3746 20.3738 12.3135L15.9002 20.335C15.0514 21.8567 14.627 22.6175 13.9905 22.898C13.6379 23.0532 13.2487 23.1075 12.8668 23.0548C12.1774 22.9593 11.5595 22.3438 10.3238 21.1128C8.71968 19.515 7.6539 18.4535 6.83882 17.9503C7.4066 17.2931 7.75 16.4366 7.75 15.5C7.75 13.4289 6.07107 11.75 4 11.75C1.92893 11.75 0.25 13.4289 0.25 15.5C0.25 17.5711 1.92893 19.25 4 19.25L4.04428 19.2497C3.91755 20.1957 4.07905 21.6973 4.32362 23.971L4.782 28.2327C5.03645 30.5982 5.24802 32.849 5.50717 34.875H42.4928C42.752 32.849 42.9635 30.5982 43.218 28.2327Z"
                  fill="#1C274C"
                />
                <path
                  class="fill-yellow-500"
                  d="M21.2803 45.5H26.7198C33.8098 45.5 37.3545 45.5 39.7198 43.383C40.7523 42.4588 41.4057 40.793 41.8775 38.625H6.1224C6.59413 40.793 7.24783 42.4588 8.2802 43.383C10.6454 45.5 14.1903 45.5 21.2803 45.5Z"
                  fill="#1C274C"
                />
              </svg>
            </div>
            <span class="menu-page-plugin-name">{{ plugin.name }}</span>
          </a>
        </li>
      </ul>
      <!-- end plugins -->
    </div>

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
      <ul class="menu-social-list">
        <li v-for="(item, id) in socialList" class="menu-social-list-item">
          <a
            :tabindex="
              menu.isDesktop ? menuIndex : menu.isActive ? menuIndex : '-1'
            "
            :href="item.href"
            target="_blank"
            :aria-labelledby="`${item}-id`"
          >
            <span :id="`${item}-id`" class="sr-only">
              {{ $t(`dashboard_menu_${item.tag}_label`) }}
            </span>
            <component :is="item.svg"></component>
          </a>
        </li>
      </ul>
      <!-- end social-->

      <!-- logout-->
      <div class="w-full">
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
