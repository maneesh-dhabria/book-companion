<script setup lang="ts">
import ConceptDetail from '@/components/concepts/ConceptDetail.vue'
import ConceptList from '@/components/concepts/ConceptList.vue'
</script>

<template>
  <div class="concepts-page">
    <div class="concepts-layout">
      <ConceptList class="list-panel" />
      <ConceptDetail class="detail-panel" />
    </div>
  </div>
</template>

<style scoped>
.concepts-page { height: 100%; }
.concepts-layout { display: grid; grid-template-columns: 320px 1fr; height: 100%; }
.list-panel { overflow-y: auto; }
.detail-panel { overflow-y: auto; }
</style>
