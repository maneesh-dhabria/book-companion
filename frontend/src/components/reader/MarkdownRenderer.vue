<script setup lang="ts">
import { classifyLink } from '@/utils/link-policy'
import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'
import { computed } from 'vue'

const props = defineProps<{
  content: string
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
  return applyLinkPolicy(sanitized)
})
</script>

<template>
  <div class="md-content" v-html="renderedHtml" />
</template>
