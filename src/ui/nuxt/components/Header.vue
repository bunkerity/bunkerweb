<script setup>
const pathSplit = useRoute().fullPath.split("/").filter(String);
</script>

<template>
  <div class="header-container">
    <header class="header-el">
      <div class="header-wrap">
        <nav>
          <!-- breadcrumb -->
          <h2 class="header-title">
            {{ pathSplit[pathSplit.length - 1] }}
          </h2>
          <ul class="header-breadcrumb-container">
            <li class="header-breadcrumb-item first">Bunkerweb</li>
            <li
              v-for="(item, id) in pathSplit"
              :class="[id === pathSplit.length - 1 ? 'active' : 'prev']"
              class="header-breadcrumb-item slash"
              :aria-current="id === pathSplit.length - 1 ? 'page' : false"
            >
              {{ item }}
            </li>
          </ul>
        </nav>
      </div>
    </header>
  </div>
</template>
