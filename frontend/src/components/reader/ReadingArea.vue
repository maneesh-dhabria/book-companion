<script setup lang="ts">
import { classifyLink } from '@/utils/link-policy'
import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'
import { computed, onMounted, onUnmounted } from 'vue'

const props = defineProps<{
  content: string
  hasPrev: boolean
  hasNext: boolean
}>()

const emit = defineEmits<{
  navigate: [direction: 'prev' | 'next']
}>()

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
  return doc.body.innerHTML
}

const renderedHtml = computed(() => {
  const raw = md.render(props.content || '')
  const sanitized = DOMPurify.sanitize(raw)
  return applyLinkPolicy(sanitized)
})

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowLeft' && props.hasPrev) emit('navigate', 'prev')
  if (e.key === 'ArrowRight' && props.hasNext) emit('navigate', 'next')
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <article class="reading-area" v-html="renderedHtml" />
</template>

<style scoped>
.reading-area {
  max-width: var(--reader-content-width, 720px);
  margin: 0 auto;
  padding: 32px 24px 64px;
  font-family: var(--reader-font-family, Georgia, 'Times New Roman', serif);
  font-size: var(--reader-font-size, 16px);
  line-height: var(--reader-line-spacing, 1.6);
  color: var(--color-text-primary);
}

.reading-area :deep(h1) { font-size: 28px; margin: 32px 0 16px; font-weight: 700; }
.reading-area :deep(h2) { font-size: 22px; margin: 28px 0 12px; font-weight: 600; }
.reading-area :deep(h3) { font-size: 18px; margin: 24px 0 10px; font-weight: 600; }
.reading-area :deep(p) { margin: 0 0 16px; }
.reading-area :deep(ul), .reading-area :deep(ol) { margin: 0 0 16px; padding-left: 24px; }
.reading-area :deep(li) { margin: 0 0 4px; }
.reading-area :deep(blockquote) {
  border-left: 3px solid var(--color-accent);
  margin: 16px 0;
  padding: 8px 16px;
  color: var(--color-text-secondary);
  background: var(--color-bg-secondary);
  border-radius: 0 4px 4px 0;
}
.reading-area :deep(code) {
  background: var(--color-bg-tertiary);
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 14px;
  font-family: 'SF Mono', Monaco, monospace;
}
.reading-area :deep(pre) {
  background: var(--color-bg-tertiary);
  padding: 16px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 0 0 16px;
}
.reading-area :deep(pre code) {
  background: none;
  padding: 0;
}
.reading-area :deep(hr) {
  border: none;
  border-top: 1px solid var(--color-border);
  margin: 32px 0;
}
.reading-area :deep(a) {
  color: var(--color-text-accent);
  text-decoration: underline;
}
</style>
