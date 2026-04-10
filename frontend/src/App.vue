<script setup lang="ts">
</script>

<template>
  <el-container style="min-height: 100vh">
    <el-header style="background: #409eff; display: flex; align-items: center; padding: 0 20px">
      <router-link to="/" style="text-decoration: none">
        <h2 style="color: #fff; margin: 0">Embedding Service</h2>
      </router-link>
    </el-header>
    <el-main style="padding: 20px; max-width: 1200px; margin: 0 auto; width: 100%">
      <router-view />
    </el-main>
  </el-container>
</template>
