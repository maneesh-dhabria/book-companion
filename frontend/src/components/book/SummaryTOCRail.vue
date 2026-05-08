<script setup lang="ts">
import MarkdownIt from 'markdown-it'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { installHeadingAnchorRuler } from '@/utils/markdownAnchors'

// Accept either rendered HTML directly or markdown source. Both paths
// produce the same heading ids because they share the slugify ruler.
const props = defineProps<{ html?: string; content?: string }>()

interface TocEntry {
  id: string
  text: string
  level: 2 | 3
}

const activeId = ref<string | null>(null)

const tocMd = new MarkdownIt({ html: false, linkify: false, typographer: false })
installHeadingAnchorRuler(tocMd)

const renderedHtml = computed(() => {
  if (props.html != null && props.html !== '') return props.html
  if (props.content != null && props.content !== '') return tocMd.render(props.content)
  return ''
})

const entries = computed<TocEntry[]>(() => {
  const html = renderedHtml.value
  if (!html) return []
  const doc = new DOMParser().parseFromString(`<div>${html}</div>`, 'text/html')
  const headings = Array.from(doc.querySelectorAll('h2[id], h3[id]'))
  const out: TocEntry[] = []
  for (const h of headings) {
    const id = h.getAttribute('id')
    if (!id) continue
    const tag = h.tagName.toLowerCase()
    if (tag !== 'h2' && tag !== 'h3') continue
    out.push({
      id,
      text: (h.textContent || '').trim(),
      level: tag === 'h2' ? 2 : 3,
    })
  }
  return out
})

let observer: IntersectionObserver | null = null

function setupObserver() {
  if (typeof IntersectionObserver === 'undefined') return
  observer?.disconnect()
  const targets = entries.value
    .map((e) => document.getElementById(e.id))
    .filter((el): el is HTMLElement => el != null)
  if (targets.length === 0) return
  observer = new IntersectionObserver(
    (records) => {
      for (const r of records) {
        if (r.isIntersecting && r.target.id) {
          activeId.value = r.target.id
          break
        }
      }
    },
    { rootMargin: '-32px 0px -60% 0px', threshold: 0 },
  )
  for (const t of targets) observer.observe(t)
}

onMounted(() => {
  setupObserver()
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
})

watch(
  () => entries.value.map((e) => e.id).join('|'),
  () => setupObserver(),
)

function isActive(id: string) {
  return activeId.value === id
}
</script>

<template>
  <nav class="toc-rail" aria-label="Summary table of contents">
    <ul v-if="entries.length > 0" class="toc-list">
      <li
        v-for="e in entries"
        :key="e.id"
        :class="['toc-item', `toc-item--h${e.level}`, { 'toc-item--active': isActive(e.id) }]"
      >
        <a :href="`#${e.id}`" class="toc-link">{{ e.text }}</a>
      </li>
    </ul>
    <ul v-else class="toc-list">
      <li class="toc-item toc-item--h2"><span class="toc-link toc-link--top">Top</span></li>
    </ul>
  </nav>
</template>

<style scoped>
.toc-rail {
  position: sticky;
  top: 64px;
  font-size: 0.85rem;
  max-height: calc(100vh - 96px);
  overflow-y: auto;
  padding: 0.25rem 0;
}

.toc-list {
  list-style: none;
  padding: 0;
  margin: 0;
  border-left: 1px solid var(--color-border, #e5e7eb);
}

.toc-item {
  padding: 0.2rem 0.75rem;
  margin-left: -1px;
  border-left: 2px solid transparent;
}

.toc-item--h3 {
  padding-left: 1.5rem;
  font-size: 0.8rem;
}

.toc-item--active {
  border-left-color: var(--color-accent, #4f46e5);
  background: var(--color-bg-secondary, #f8fafc);
}

.toc-link {
  color: var(--color-text-secondary, #475569);
  text-decoration: none;
  display: block;
}

.toc-item--active .toc-link {
  color: var(--color-text-primary, #0f172a);
  font-weight: 500;
}

.toc-link:hover {
  color: var(--color-text-primary, #0f172a);
}

.toc-link--top {
  cursor: default;
}
</style>
