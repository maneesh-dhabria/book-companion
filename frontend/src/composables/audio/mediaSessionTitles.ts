/**
 * FR-19 / FR-19b / plan T18: deterministic title for navigator.mediaSession
 * metadata, varied by content type so the OS Now Playing widget shows
 * meaningful labels (macOS menubar, Android notification shade, etc.).
 */
export function titleForContentType(contentType: string | undefined): string {
  switch (contentType) {
    case 'section_summary':
      return 'Section summary'
    case 'book_summary':
      return 'Book summary'
    case 'section_content':
      return 'Section content'
    case 'annotation':
      return 'Annotation'
    case 'annotations_playlist':
      return 'Annotations playlist'
    default:
      return 'Audio'
  }
}
