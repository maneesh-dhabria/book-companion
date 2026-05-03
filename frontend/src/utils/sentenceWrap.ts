/**
 * Wrap each sentence in `<span class="bc-sentence" data-sentence-index="N">`.
 *
 * Boundaries are character offsets into the cumulative *text* of all
 * block-level elements (`<p>`, `<li>`, `<blockquote>`, `<h1..h6>`). Sentences
 * never span across block boundaries — when a block ends mid-sentence the
 * remainder of that sentence stays in-block and the next block starts a new
 * (potentially same-index) sentence. Anchor and inline children are preserved.
 */
const BLOCK_SELECTOR = 'p, li, blockquote, h1, h2, h3, h4, h5, h6'

interface OffsetEntry {
  start: number
  index: number
}

export function wrapSentences(html: string, sentenceOffsetsChars: number[]): string {
  if (!sentenceOffsetsChars || sentenceOffsetsChars.length === 0) return html
  const doc = new DOMParser().parseFromString(`<div>${html}</div>`, 'text/html')
  const root = doc.body.firstElementChild as HTMLElement | null
  if (!root) return html

  const offsets: OffsetEntry[] = sentenceOffsetsChars.map((start, index) => ({
    start,
    index,
  }))

  let cumulative = 0
  for (const block of Array.from(root.querySelectorAll(BLOCK_SELECTOR))) {
    cumulative = wrapBlock(doc, block as HTMLElement, offsets, cumulative)
  }
  return root.innerHTML
}

function wrapBlock(
  doc: Document,
  block: HTMLElement,
  offsets: OffsetEntry[],
  startCumulative: number,
): number {
  // Skip nested blocks — they are handled by the outer querySelectorAll loop.
  // (querySelectorAll visits descendants in document order, including
  // nested ones, so inner blocks are wrapped on their own iteration.)
  const text = block.textContent ?? ''
  if (text.length === 0) return startCumulative
  const blockStart = startCumulative
  const blockEnd = blockStart + text.length

  // Find offsets that intersect this block.
  const intersecting = offsets.filter((o) => o.start < blockEnd)
  if (intersecting.length === 0) return blockEnd

  // Determine in-block boundaries: relative to text start.
  const localBoundaries: { localStart: number; index: number }[] = []
  for (const o of intersecting) {
    const localStart = Math.max(0, o.start - blockStart)
    if (localStart < text.length) {
      localBoundaries.push({ localStart, index: o.index })
    }
  }
  if (localBoundaries.length === 0) return blockEnd

  // Ensure first boundary covers the start of the block.
  if (localBoundaries[0].localStart > 0) {
    // The block starts mid-sentence — we still wrap that fragment as the
    // most recently started sentence (one less than first local boundary).
    const prevIdx = localBoundaries[0].index - 1
    if (prevIdx >= 0) {
      localBoundaries.unshift({ localStart: 0, index: prevIdx })
    } else {
      localBoundaries.unshift({ localStart: 0, index: localBoundaries[0].index })
    }
  }

  // Collect direct text children flat — ignore nested block children to
  // avoid double-wrapping; we only wrap text node runs in this block.
  // Collect text nodes via TreeWalker but stop descending into nested blocks.
  const textNodes: Text[] = []
  collectTextNodes(block, textNodes)
  if (textNodes.length === 0) return blockEnd

  // Build a flat scan: walk text nodes, when we cross a boundary split.
  let pos = 0
  for (const node of textNodes) {
    const nodeText = node.data
    if (nodeText.length === 0) continue
    const fragments: { idx: number; text: string }[] = []
    let cursor = 0
    while (cursor < nodeText.length) {
      const absPos = pos + cursor
      // Find sentence index covering absPos.
      let activeIdx = localBoundaries[0].index
      let nextBoundary = nodeText.length
      for (let i = 0; i < localBoundaries.length; i++) {
        const b = localBoundaries[i]
        if (b.localStart <= absPos) {
          activeIdx = b.index
          nextBoundary =
            i + 1 < localBoundaries.length
              ? Math.min(nodeText.length, localBoundaries[i + 1].localStart - pos)
              : nodeText.length
        } else {
          break
        }
      }
      const end = Math.min(nodeText.length, nextBoundary)
      fragments.push({ idx: activeIdx, text: nodeText.slice(cursor, end) })
      cursor = end
    }
    // Replace node with fragments wrapped in spans.
    const parent = node.parentNode
    if (!parent) continue
    const replacement = doc.createDocumentFragment()
    for (const f of fragments) {
      if (f.text.length === 0) continue
      const span = doc.createElement('span')
      span.className = 'bc-sentence'
      span.setAttribute('data-sentence-index', String(f.idx))
      span.textContent = f.text
      replacement.appendChild(span)
    }
    parent.replaceChild(replacement, node)
    pos += nodeText.length
  }

  return blockEnd
}

function collectTextNodes(root: HTMLElement, out: Text[]): void {
  for (const child of Array.from(root.childNodes)) {
    if (child.nodeType === Node.TEXT_NODE) {
      out.push(child as Text)
    } else if (child.nodeType === Node.ELEMENT_NODE) {
      const el = child as HTMLElement
      if (el.matches(BLOCK_SELECTOR)) {
        // Skip — the outer loop will visit this nested block separately.
        continue
      }
      collectTextNodes(el, out)
    }
  }
}
