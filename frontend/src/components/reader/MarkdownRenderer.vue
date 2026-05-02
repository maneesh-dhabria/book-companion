<script setup lang="ts">
import type { AnnotationLike } from '@/utils/highlightInjector'
import { applyHighlights } from '@/utils/highlightInjector'
import { classifyLink } from '@/utils/link-policy'
import { wrapSentences } from '@/utils/sentenceWrap'
import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import { useTtsPlayerStore } from '@/stores/ttsPlayer'

const props = withDefaults(
  defineProps<{
    content: string
    annotations?: AnnotationLike[]
    highlightsInline?: boolean
    sentenceOffsetsChars?: number[]
  }>(),
  { annotations: () => [], highlightsInline: true, sentenceOffsetsChars: () => [] },
)

// Tolerate test environments without an active Pinia: when no store is
// available we simply skip the active-sentence highlight pass.
const ttsPlayer = (() => {
  try {
    return useTtsPlayerStore()
  } catch {
    return null
  }
})()
const containerRef = ref<HTMLElement | null>(null)

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
})

function applyLinkPolicy(sanitized: string): string {
  const doc = new DOMParser().parseFromString(sanitized, 'text/html')
  for (const a of Array.from(doc.querySelectorAll('a[href]'))) {
    const cls = classifyLink(a.getAttribute('href') || '')
    if (cls === 'external') {
      a.setAttribute('target', '_blank')
      a.setAttribute('rel', 'noopener noreferrer')
    } else {
      const span = doc.createElement('span')
      span.textContent = a.textContent || ''
      if (a.className) span.className = a.className
      a.replaceWith(span)
    }
  }
  // Decorative image sweep (FR-E7.1): images whose alt is the literal
  // placeholder "image" are treated as decorative and get alt="" so
  // screen readers skip them. Tiny 1-px-tall images are also decorative
  // but that requires DOM inspection of the rendered image which happens
  // post-mount; the alt==='image' case is the common EPUB output.
  for (const img of Array.from(doc.querySelectorAll('img'))) {
    if (img.getAttribute('alt') === 'image') {
      img.setAttribute('alt', '')
    }
  }
  return doc.body.innerHTML
}

const renderedHtml = computed(() => {
  const raw = md.render(props.content || '')
  const sanitized = DOMPurify.sanitize(raw)
  const linkSafe = applyLinkPolicy(sanitized)
  const withHighlights = applyHighlights(linkSafe, props.annotations || [], {
    showInline: props.highlightsInline,
  })
  if (props.sentenceOffsetsChars && props.sentenceOffsetsChars.length > 0) {
    return wrapSentences(withHighlights, props.sentenceOffsetsChars)
  }
  return withHighlights
})

function applyActiveSentence(): void {
  if (!ttsPlayer) return
  const root = containerRef.value
  if (!root) return
  const idx = ttsPlayer.sentenceIndex
  for (const el of Array.from(root.querySelectorAll('.bc-sentence-active'))) {
    el.classList.remove('bc-sentence-active')
  }
  const target = root.querySelector(`.bc-sentence[data-sentence-index="${idx}"]`)
  if (target) target.classList.add('bc-sentence-active')
}

onMounted(() => {
  void nextTick(applyActiveSentence)
})

if (ttsPlayer) {
  watch(
    () => [renderedHtml.value, ttsPlayer.sentenceIndex],
    () => {
      void nextTick(applyActiveSentence)
    },
  )
}
</script>

<template>
  <div ref="containerRef" class="md-content markdown-body" v-html="renderedHtml" />
</template>

<style scoped>
.markdown-body :deep(ul) {
  list-style-type: disc;
  padding-left: 1.5em;
  margin: 0.5em 0 1em;
}
.markdown-body :deep(ul ul) {
  list-style-type: circle;
}
.markdown-body :deep(ul ul ul) {
  list-style-type: square;
}
.markdown-body :deep(ol) {
  list-style-type: decimal;
  padding-left: 1.75em;
  margin: 0.5em 0 1em;
}
.markdown-body :deep(li) {
  margin: 0.25em 0;
}
.markdown-body :deep(table) {
  border-collapse: collapse;
  margin: 1em 0;
  width: 100%;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--reader-border, var(--color-border));
  padding: 0.4em 0.75em;
  text-align: left;
}
.markdown-body :deep(thead) {
  background: var(--reader-surface-muted, var(--color-bg-muted, transparent));
  font-weight: 600;
}
</style>
