<script setup>
import MenuSvgHome from "./Menu/Svg/Home.vue";
import MenuSvgInstances from "./Menu/Svg/Instances.vue";
import MenuSvgGlobalConf from "./Menu/Svg/GloMenuSvgGlobalConf.vue";
import MenuSvgConfigs from "./Menu/Svg/Configs.vue";
import MenuSvgPlugins from "./Menu/Svg/Plugins.vue";
import MenuSvgJobs from "./Menu/Svg/Jobs.vue";
import MenuSvgTwitter from "./Menu/Svg/Twitter.vue";
import MenuSvgLinkedin from "./Menu/Svg/Linkedin.vue";
import MenuSvgDiscord from "./Menu/Svg/Discord.vue";
import MenuSvgGithub from "./Menu/Svg/Github.vue";
const route = useRoute();
const currPath = route.path;

// Navigation with components
// resolveComponent allow to replace a tag by a real Vue component
const navList = [
  { title: "Home", svg: resolveComponent(MenuSvgHome), path: "/admin/home" },
  {
    title: "Instances",
    svg: resolveComponent(MenuSvgInstances),
    path: "/admin/instances",
  },
  {
    title: "Global config",
    svg: resolveComponent(MenuSvgGlobalConf),
    path: "/admin/global-config",
  },
  {
    title: "Configs",
    svg: resolveComponent(MenuSvgConfigs),
    path: "/admin/configs",
  },
  {
    title: "Plugins",
    svg: resolveComponent(MenuSvgPlugins),
    path: "/admin/plugins",
  },
  { title: "Jobs", svg: resolveComponent(MenuSvgJobs), path: "/admin/jobs" },
];

// Social links
const socialList = [
  {
    title: "link to Twitter",
    href: "https://twitter.com/bunkerity",
    svg: resolveComponent(MenuSvgTwitter),
  },
  {
    title: "link to Linkedin",
    href: "https://www.linkedin.com/company/bunkerity/",
    svg: resolveComponent(MenuSvgLinkedin),
  },
  {
    title: "link to Discord",
    href: "https://discord.gg/fTf46FmtyD",
    svg: resolveComponent(MenuSvgDiscord),
  },
  {
    title: "link to Github",
    href: "https://github.com/bunkerity",
    svg: resolveComponent(MenuSvgGithub),
  },
];

const menu = reactive({
  pagePlugins: [], // Render custom page plugins links
  darkMode: useDarkMode(), // Apply dark mode state
  isActive: false, // Handle menu display/expand
  isDesktop: true, // Expand logic exclude with desktop
});

// Check device desktop using breakpoint
onMounted(() => {
  menu.isDesktop = window.innerWidth < 1200 ? false : true;
  window.addEventListener("resize", () => {
    menu.isDesktop = window.innerWidth < 1200 ? false : true;
  });
});

// EVENTS

// Toggle dark mode
function switchMode() {
  menu.darkMode = menu.darkMode ? false : true;
  menu.darkMode
    ? document.querySelector("html").classList.add("dark")
    : document.querySelector("html").classList.remove("dark");
}

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
    :aria-checked="menu.isDesktop ? 'true' : menu.isActive ? 'true' : 'false'"
    aria-describedby="sidebar-menu"
    type="button"
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
    :class="[menu.isActive ? '' : '-translate-x-full']"
    class="menu-container xl:translate-x-0"
    :aria-expanded="menu.isDesktop ? 'true' : menu.isActive ? 'true' : 'false'"
    :aria-hidden="menu.isDesktop ? 'false' : menu.isActive ? 'false' : 'true'"
  >
    <!-- close btn-->
    <svg
      type="button"
      @click="closeMenu()"
      data-sidebar-menu-close
      class="menu-close-btn"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 320 512"
    >
      <path
        d="M310.6 150.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L160 210.7 54.6 105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L114.7 256 9.4 361.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 301.3 265.4 406.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L205.3 256 310.6 150.6z"
      />
    </svg>
    <!-- close btn-->
    <!-- top sidebar -->
    <div class="w-full">
      <!-- logo and version -->
      <div class="h-19">
        <a
          class="menu-logo-container"
          :href="currPath === '/home' ? '#' : '/home'"
        >
          <img
            src="/images/logo-menu-2.png"
            class="menu-logo-dark"
            alt="main logo dark"
          />
          <img
            src="/images/logo-menu.png"
            class="menu-logo-light"
            alt="main logo light"
          />
        </a>
      </div>

      <hr class="menu-separator" />
      <!-- end logo version -->

      <!-- list items -->
      <div class="menu-nav-list-container h-full">
        <ul class="menu-nav-list">
          <!-- item -->
          <li v-for="item in navList" class="mt-0.5 w-full">
            <a
              :class="[
                item.path === currPath ? 'active' : '',
                'menu-nav-item-anchor',
              ]"
              :href="item.path === currPath ? '#' : item.path"
            >
              <div class="menu-nav-item-container">
                <component :is="item.svg"></component>
              </div>
              <span class="menu-nav-item-title">{{ item.title }}</span>
            </a>
          </li>
          <!-- end item -->
        </ul>
        <!-- end default anchor -->

        <div>
          <!-- plugins -->
          <ul>
            <li class="w-full mt-4">
              <h6 class="menu-page-plugin-title">PLUGIN PAGES</h6>
            </li>
            <li v-if="menu.pagePlugins.length === 0" class="w-full mt-8">
              <h6 class="menu-page-plugin-empty-title">
                Want your own plugins ? <br />
                <a
                  class="menu-page-plugin-empty-anchor"
                  target="_blank"
                  href="https://docs.bunkerweb.io/1.4/plugins/#writing-a-plugin"
                  >check doc</a
                >
              </h6>
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
    <div class="w-full flex flex-col justify-end m-4">
      <!-- dark/light mode -->
      <div class="menu-mode-container">
        <input
          type="hidden"
          id="csrf_token"
          name="csrf_token"
          :value="menu.csrfToken"
        />
        <input
          :checked="menu.darkMode"
          @click="switchMode()"
          id="darkMode"
          data-dark-toggle
          class="menu-mode-checkbox"
          type="checkbox"
        />
        <label for="darkMode" data-dark-toggle-label class="menu-mode-label">
          {{ menu.darkMode ? "dark mode" : "light mode" }}
        </label>
      </div>
      <!-- end dark/light mode -->

      <!-- social-->
      <ul class="menu-social-list">
        <li v-for="item in socialList" class="mx-2 w-6">
          <a :href="item.href" target="_blank">
            <span class="sr-only">{{ item.title }}</span>
            <component :is="item.svg"></component>
          </a>
        </li>
      </ul>
      <!-- end social-->

      <!-- logout-->
      <div class="w-full">
        <a
          href="/logout"
          class="tracking-wide dark:brightness-125 hover:brightness-75 w-full inline-block px-6 py-3 font-bold text-center text-white uppercase align-middle transition-all rounded-lg cursor-pointer bg-gradient-to-tl bg-primary leading-normal text-xs ease-in shadow-xs bg-150 bg-x-25 hover:-translate-y-px active:opacity-85 hover:shadow-md"
        >
          Logout
        </a>
      </div>
      <!-- end logout-->
    </div>
    <!-- end bottom sidebar  -->
  </aside>
  <!-- end left sidebar -->
</template>
