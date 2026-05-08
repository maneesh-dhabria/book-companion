// FR-C07 — slugify + markdown-it ruler that emits stable id="<slug>" on
// every h2/h3. The `taken` set is created INSIDE the closure so collisions
// reset per render() call. Used by MarkdownRenderer and SummaryTOCRail so
// the TOC links match the rendered heading ids exactly.
import type MarkdownIt from 'markdown-it'

export function slugify(
  text: string,
  taken: Set<string>,
  fallbackOrdinal: number,
): string {
  let base = text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
  if (!base) base = `section-${fallbackOrdinal}`
  if (!taken.has(base)) {
    taken.add(base)
    return base
  }
  let n = 1
  while (taken.has(`${base}-${n}`)) n++
  const final = `${base}-${n}`
  taken.add(final)
  return final
}

export function installHeadingAnchorRuler(md: MarkdownIt): void {
  md.core.ruler.push('heading_anchor_ids', (state) => {
    const taken = new Set<string>()
    let headingOrdinal = 0
    const tokens = state.tokens
    for (let i = 0; i < tokens.length; i++) {
      const t = tokens[i]
      if (t.type !== 'heading_open') continue
      if (t.tag !== 'h2' && t.tag !== 'h3') continue
      const inline = tokens[i + 1]
      const text = inline && inline.type === 'inline' ? inline.content : ''
      const id = slugify(text, taken, headingOrdinal)
      t.attrSet('id', id)
      headingOrdinal++
    }
  })
}
