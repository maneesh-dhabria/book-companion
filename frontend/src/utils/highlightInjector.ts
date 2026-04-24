/**
 * Post-DOMPurify highlight injector (FR-C5.x).
 *
 * Takes sanitized HTML + an annotation set and returns the same HTML with
 * `<mark data-annotation-id="{N}">...</mark>` wrappers around each
 * annotation's selected text. When an annotation range spans multiple
 * block-level elements, we emit one mark per block and all share the same
 * ``data-annotation-id``; only the first block's mark receives
 * ``id="ann-{N}"`` so the cross-section scroll anchor is unambiguous.
 *
 * Anchoring is hybrid:
 *   1. Try ``text_start``/``text_end`` offsets against the plaintext view.
 *   2. If offsets don't align to the exact ``selected_text``, fall back to
 *      searching for ``selected_text`` with ``prefix``/``suffix`` context
 *      to disambiguate repeated occurrences.
 *   3. If neither succeeds, the annotation is skipped silently (the UI
 *      sidebar still shows it — we just don't inline-highlight).
 */

const BLOCK_TAGS = new Set([
  'P',
  'DIV',
  'LI',
  'UL',
  'OL',
  'BLOCKQUOTE',
  'H1',
  'H2',
  'H3',
  'H4',
  'H5',
  'H6',
  'PRE',
  'TABLE',
  'TR',
  'TD',
  'TH',
  'SECTION',
  'ARTICLE',
])

export interface AnnotationLike {
  id: number
  text_start?: number | null
  text_end?: number | null
  selected_text?: string | null
  prefix?: string | null
  suffix?: string | null
}

export interface InjectorOptions {
  showInline: boolean
}

/** Return the nearest block-level ancestor of a node (or the document root). */
function blockAncestor(node: Node, root: Node): Element {
  let cur: Node | null = node
  while (cur && cur !== root) {
    if (cur.nodeType === Node.ELEMENT_NODE) {
      const el = cur as Element
      if (BLOCK_TAGS.has(el.tagName)) return el
    }
    cur = cur.parentNode
  }
  return root as Element
}

/**
 * Compute a (node, offsetInNode) pair for a given plaintext character offset
 * inside ``root``. Returns null when the offset is out of range.
 */
function textPositionAt(
  root: Node,
  targetOffset: number,
): { node: Text; offset: number } | null {
  const walker = (root.ownerDocument || document).createTreeWalker(
    root,
    NodeFilter.SHOW_TEXT,
  )
  let remaining = targetOffset
  let current = walker.nextNode()
  while (current) {
    const t = current as Text
    const len = t.data.length
    if (remaining <= len) {
      return { node: t, offset: remaining }
    }
    remaining -= len
    current = walker.nextNode()
  }
  return null
}

function plainText(root: Node): string {
  return (root.textContent || '').replace(/\s+/g, ' ')
}

/**
 * Find a plaintext offset for ``selected_text`` disambiguated by prefix + suffix.
 * Returns -1 when no occurrence matches the context.
 */
function findWithContext(
  haystack: string,
  needle: string,
  prefix: string,
  suffix: string,
): number {
  if (!needle) return -1
  if (!prefix && !suffix) return haystack.indexOf(needle)
  let idx = 0
  // Walk every occurrence, return the first whose prefix/suffix align.
  while (true) {
    const at = haystack.indexOf(needle, idx)
    if (at === -1) return -1
    const before = haystack.slice(Math.max(0, at - prefix.length), at)
    const after = haystack.slice(at + needle.length, at + needle.length + suffix.length)
    const prefixOk = !prefix || before.endsWith(prefix)
    const suffixOk = !suffix || after.startsWith(suffix)
    if (prefixOk && suffixOk) return at
    idx = at + 1
  }
}

function wrapRange(
  doc: Document,
  root: Node,
  start: number,
  end: number,
  annotationId: number,
  isFirstRangeForAnnotation: boolean,
): boolean {
  const startPos = textPositionAt(root, start)
  const endPos = textPositionAt(root, end)
  if (!startPos || !endPos) return false

  const range = doc.createRange()
  range.setStart(startPos.node, startPos.offset)
  range.setEnd(endPos.node, endPos.offset)

  // Split the range into sub-ranges aligned to block-level ancestors.
  const startBlock = blockAncestor(startPos.node, root)
  const endBlock = blockAncestor(endPos.node, root)
  if (startBlock === endBlock) {
    return wrapSingleRange(doc, range, annotationId, isFirstRangeForAnnotation)
  }

  // Multi-block range — wrap from start..endOfStartBlock, then each middle
  // block fully, then startOfEndBlock..end.
  let firstEmitted = false
  const midBlocks: Element[] = []

  // Iterate sibling chain between startBlock and endBlock.
  let cur: Node | null = startBlock.nextSibling
  while (cur && cur !== endBlock) {
    if (cur.nodeType === Node.ELEMENT_NODE && BLOCK_TAGS.has((cur as Element).tagName)) {
      midBlocks.push(cur as Element)
    }
    cur = cur.nextSibling
  }

  // start...endOfStartBlock
  const headRange = doc.createRange()
  headRange.setStart(startPos.node, startPos.offset)
  headRange.setEnd(startBlock, startBlock.childNodes.length)
  firstEmitted =
    wrapSingleRange(doc, headRange, annotationId, isFirstRangeForAnnotation) ||
    firstEmitted

  for (const b of midBlocks) {
    const r = doc.createRange()
    r.selectNodeContents(b)
    wrapSingleRange(doc, r, annotationId, false)
  }

  // start of endBlock ... end
  const tailRange = doc.createRange()
  tailRange.setStart(endBlock, 0)
  tailRange.setEnd(endPos.node, endPos.offset)
  wrapSingleRange(doc, tailRange, annotationId, false)

  return firstEmitted
}

function wrapSingleRange(
  doc: Document,
  range: Range,
  annotationId: number,
  attachScrollId: boolean,
): boolean {
  if (range.collapsed) return false
  try {
    const mark = doc.createElement('mark')
    mark.setAttribute('data-annotation-id', String(annotationId))
    if (attachScrollId) mark.setAttribute('id', `ann-${annotationId}`)
    range.surroundContents(mark)
    return true
  } catch {
    // surroundContents throws when the range crosses non-text boundaries.
    // Degrade: walk text nodes inside the range and wrap each individually.
    return wrapAcrossNodes(doc, range, annotationId, attachScrollId)
  }
}

function wrapAcrossNodes(
  doc: Document,
  range: Range,
  annotationId: number,
  attachScrollId: boolean,
): boolean {
  const walker = doc.createTreeWalker(
    range.commonAncestorContainer,
    NodeFilter.SHOW_TEXT,
  )
  const toWrap: Text[] = []
  while (walker.nextNode()) {
    const n = walker.currentNode as Text
    if (range.intersectsNode(n)) toWrap.push(n)
  }
  let first = true
  for (const t of toWrap) {
    const start = t === range.startContainer ? range.startOffset : 0
    const end = t === range.endContainer ? range.endOffset : t.data.length
    if (end <= start) continue
    const before = t.data.slice(0, start)
    const middle = t.data.slice(start, end)
    const after = t.data.slice(end)
    const mark = doc.createElement('mark')
    mark.setAttribute('data-annotation-id', String(annotationId))
    if (attachScrollId && first) mark.setAttribute('id', `ann-${annotationId}`)
    mark.textContent = middle
    const parent = t.parentNode!
    if (before) parent.insertBefore(doc.createTextNode(before), t)
    parent.insertBefore(mark, t)
    if (after) parent.insertBefore(doc.createTextNode(after), t)
    parent.removeChild(t)
    first = false
  }
  return toWrap.length > 0
}

/**
 * Entry point. Given sanitized HTML + annotations + options, return HTML
 * with `<mark>` wrappers injected. Pure function: no DOM mutation outside
 * the detached DOMParser document.
 */
export function applyHighlights(
  html: string,
  annotations: AnnotationLike[],
  options: InjectorOptions,
): string {
  if (!options.showInline || !annotations.length) return html
  const parser = new DOMParser()
  const wrap = `<div id="__hi_root__">${html}</div>`
  const doc = parser.parseFromString(wrap, 'text/html')
  const root = doc.getElementById('__hi_root__')
  if (!root) return html

  for (const ann of annotations) {
    if (!ann.selected_text) continue
    const text = plainText(root)
    let offset = -1
    if (
      typeof ann.text_start === 'number' &&
      typeof ann.text_end === 'number' &&
      ann.text_end > ann.text_start
    ) {
      const candidate = text.slice(ann.text_start, ann.text_end)
      if (candidate === ann.selected_text) offset = ann.text_start
    }
    if (offset === -1) {
      offset = findWithContext(
        text,
        ann.selected_text,
        ann.prefix || '',
        ann.suffix || '',
      )
    }
    if (offset === -1) continue
    const end = offset + ann.selected_text.length
    wrapRange(doc, root, offset, end, ann.id, true)
  }

  return root.innerHTML
}
