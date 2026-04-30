<script setup lang="ts">
/**
 * Standalone post-summary structure-editing view (T22 / D9).
 * Hosted at /books/:id/edit-structure.
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import StructureEditor from '@/components/upload/StructureEditor.vue'

const route = useRoute()
const router = useRouter()

const bookId = computed(() => Number(route.params.id))

function done() {
  router.push(`/books/${bookId.value}`)
}
</script>

<template>
  <div class="mx-auto max-w-4xl px-4 py-6">
    <StructureEditor
      :book-id="bookId"
      mode="post-summary"
      @complete="done"
      @back="done"
    />
  </div>
</template>
