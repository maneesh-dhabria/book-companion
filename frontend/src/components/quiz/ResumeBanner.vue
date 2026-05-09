<template>
  <div data-test="resume-banner" class="resume-banner" role="status">
    <span>{{ COPY.resumeBanner }}</span>
    <button type="button" data-test="resume-btn" @click="$emit('resume')">
      {{ COPY.resumeButton }}
    </button>
    <button type="button" data-test="stop-btn" @click="$emit('stop')">
      {{ COPY.stopAndStartButton }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { COPY } from './copy'

defineProps<{ session: { id: number } }>()
defineEmits<{ resume: []; stop: [] }>()
</script>
