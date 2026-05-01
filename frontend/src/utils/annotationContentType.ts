/**
 * Map the active reader-tab mode to the annotation content_type that new
 * highlights/notes should be stored against.
 *
 * - 'summary' tab → annotations on the section's summary body
 * - 'original' tab → annotations on the raw section content
 */
export type ReaderActiveTab = 'summary' | 'original'

export const annotationContentTypeFor = (
  activeTab: ReaderActiveTab,
): 'section_summary' | 'section_content' =>
  activeTab === 'summary' ? 'section_summary' : 'section_content'
