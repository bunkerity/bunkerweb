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
import { reactive, onMounted } from "vue";
import { getDarkMode } from "@utils/global.js";
import { getCookie } from "@utils/api";

async function getlogout() {
  fetch("/logout", {
    method: "post",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-TOKEN": getCookie("csrf_access_token"),
    },
  })
    .then((res) => {
      return res.json();
    })
    .then((data) => {
      if (data.type === "success")
        return (window.location = `${window.location.origin}/admin/login`);
    })
    .catch((err) => {});
}

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

// Check device desktop using breakpoint
onMounted(() => {
  // Get current mode from sessionStorage and update
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
});

// EVENTS

// Close the menu, desktop exclude
function closeMenu() {
  menu.isActive = false;
}

function toggleMenu() {
  menu.isActive = menu.isActive ? false : true;
}
</script>

<template>
  <!-- float button-->
  <button
    aria-controls="sidebar-menu"
    @click="toggleMenu()"
    class="menu-float-btn"
  >
    <svg
      fill="#0D6EFD"
      class="h-6 w-6 translate-x-0.5"
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
    :class="[menu.isDesktop ? true : menu.isActive ? '' : 'active']"
    class="menu-container xl:translate-x-0"
    :aria-expanded="menu.isDesktop ? 'true' : menu.isActive ? 'true' : 'false'"
  >
    <!-- close btn-->
    <button data-sidebar-menu-close @click="closeMenu()">
      <svg
        class="menu-close-btn"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 320 512"
      >
        <path
          d="M310.6 150.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L160 210.7 54.6 105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L114.7 256 9.4 361.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 301.3 265.4 406.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L205.3 256 310.6 150.6z"
        />
      </svg>
    </button>

    <!-- close btn-->
    <!-- top sidebar -->
    <div class="w-full">
      <!-- logo and version -->
      <div class="h-19">
        <a
          class="menu-logo-container"
          :href="menu.currPath === '/home' ? '#' : '/home'"
        >
          <img
            src="/images/logo-menu-2.png"
            class="menu-logo-dark"
            :alt="$t('dashboard_logo_alt')"
          />
          <img
            src="/images/logo-menu.png"
            class="menu-logo-light"
            :alt="$t('dashboard_logo_alt')"
          />
        </a>
      </div>

      <hr class="menu-separator" />
      <!-- end logo version -->

      <!-- list items -->
      <div class="menu-nav-list-container h-full">
        <ul class="menu-nav-list">
          <!-- item -->
          <li v-for="(item, id) in navList" :key="id" class="mt-0.5 w-full">
            <a
              :class="[
                item.path.toLowerCase().includes(menu.currPath) ? 'active' : '',
                'menu-nav-item-anchor',
              ]"
              :href="
                item.path.toLowerCase().includes(menu.currPath)
                  ? '#'
                  : item.path
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

        <div>
          <!-- plugins -->
          <ul>
            <li class="w-full mt-4">
              <p class="menu-page-plugin-title">
                {{ $t("dashboard_menu_plugins_title") }}
              </p>
            </li>
            <li v-if="menu.pagePlugins.length === 0" class="w-full mt-6">
              <div class="menu-page-plugin-empty-title">
                {{ $t("dashboard_menu_plugins_none") }} <br />
                <a
                  class="menu-page-plugin-empty-anchor"
                  target="_blank"
                  href="https://docs.bunkerweb.io/latest/plugins?utm_campaign=self&utm_source=ui"
                >
                  {{ $t("dashboard_menu_plugins_none_doc") }}
                </a>
              </div>
            </li>

            <li v-for="plugin in menu.pagePlugins" class="mt-0.5 w-full">
              <a
                target="_blank"
                class="menu-page-plugin-anchor"
                :href="`/plugins?plugin_id=${plugin.id}`"
              >
                <div class="menu-page-plugin-svg-container">
                  <svg
                    class="fill-amber-500 h-5 w-5 relative"
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 384 512"
                  >
                    <path
                      d="M0 64C0 28.7 28.7 0 64 0H224V128c0 17.7 14.3 32 32 32H384V448c0 35.3-28.7 64-64 64H64c-35.3 0-64-28.7-64-64V64zm384 64H256V0L384 128z"
                    />
                  </svg>
                </div>
                <span class="menu-page-plugin-name">{{ plugin.name }}</span>
              </a>
            </li>
          </ul>
          <!-- end plugins -->
        </div>
      </div>
      <!-- end list items -->
    </div>
    <!-- end top sidebar -->

    <!-- bottom sidebar  -->
    <div class="w-full flex flex-col justify-end mt-2 m-4">
      <hr class="line-separator" />

      <!-- dark/light mode -->
      <div class="menu-mode-container">
        <input
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
        <li v-for="item in socialList" class="mx-2 w-6">
          <a :href="item.href" target="_blank">
            <span class="sr-only">
              {{ $t(`dashboard_link_${item.tag}`) }}
            </span>
            <component :is="item.svg"></component>
          </a>
        </li>
      </ul>
      <!-- end social-->

      <!-- logout-->
      <div class="w-full">
        <button @click="getlogout()" class="menu-logout">
          {{ $t("dashboard_menu_log_out") }}
        </button>
      </div>
      <!-- end logout-->
    </div>
    <!-- end bottom sidebar  -->
  </aside>
  <!-- end left sidebar -->
</template>
