/**
 * Turn a raw snake_case / kebab-case / lowerCamelCase identifier into a
 * reader-facing label.
 *
 *   labelize('table_of_contents')    → 'Table of Contents'
 *   labelize('practitioner_bullets') → 'Practitioner Bullets'
 *   labelize('EPUB')                 → 'EPUB'                // preserved
 *   labelize('frankenstein_epub')    → 'Frankenstein EPUB'   // acronym retained
 */

const ACRONYMS = new Set(['EPUB', 'PDF', 'MOBI', 'HTML', 'URL', 'API', 'AI', 'LLM'])

const STOP_WORDS = new Set(['of', 'the', 'and', 'or', 'for', 'a', 'in', 'on', 'to'])

function capitalize(word: string): string {
  if (word.length === 0) return word
  return word[0].toUpperCase() + word.slice(1).toLowerCase()
}

export function labelize(input: string | null | undefined): string {
  if (input == null || input === '') return ''
  const trimmed = input.trim()
  if (ACRONYMS.has(trimmed)) return trimmed
  const parts = trimmed.split(/[_\-\s]+/).filter(Boolean)
  return parts
    .map((part, idx) => {
      const upper = part.toUpperCase()
      if (ACRONYMS.has(upper)) return upper
      if (idx > 0 && STOP_WORDS.has(part.toLowerCase())) {
        return part.toLowerCase()
      }
      return capitalize(part)
    })
    .join(' ')
}
