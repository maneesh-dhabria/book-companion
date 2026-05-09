export interface Author {
  id: number
  name: string
  role: string
}

export interface BookListItem {
  id: number
  title: string
  status: string
  file_format: string
  file_size_bytes: number
  authors: Author[]
  section_count: number
  cover_url: string | null
  has_summary: boolean
  eval_passed: number | null
  eval_total: number | null
  created_at: string
  updated_at: string
  // v1.5 — optional; library-list response doesn't always include these.
  tags?: { id: number; name: string; color: string | null }[]
}

export interface SectionBrief {
  id: number
  title: string
  order_index: number
  section_type: string
  content_token_count: number | null
  content_char_count: number | null
  has_summary: boolean
  default_summary?: SummaryBrief | null
  last_failure_type?: string | null
}

export interface SummaryProgress {
  summarized: number
  total: number
}

export interface Book {
  id: number
  title: string
  status: string
  file_format: string
  file_size_bytes: number
  file_hash: string
  authors: Author[]
  sections: SectionBrief[]
  section_count: number
  cover_url: string | null
  created_at: string
  updated_at: string
  summary_progress?: SummaryProgress | null
  default_summary?: SummaryBrief | null
  last_used_preset?: string | null
}

export interface Section {
  id: number
  book_id: number
  title: string
  order_index: number
  section_type: string
  content_token_count: number | null
  content_char_count?: number | null
  content_md: string | null
  default_summary: SummaryBrief | null
  summary_count: number
  annotation_count: number
  has_summary: boolean
  is_summarizable?: boolean
}

export interface SummaryBrief {
  id: number
  preset_name: string | null
  model_used: string
  summary_char_count: number
  created_at: string
  summary_md?: string | null
}

export interface Summary {
  id: number
  content_type: string
  content_id: number
  book_id: number
  preset_name: string | null
  facets_used: Record<string, unknown>
  model_used: string
  input_tokens: number | null
  output_tokens: number | null
  input_char_count: number
  summary_char_count: number
  summary_md: string
  eval_json: Record<string, unknown> | null
  quality_warnings: Record<string, unknown> | null
  latency_ms: number | null
  created_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface ErrorResponse {
  detail: string
  code: string
}

export interface ProcessingStatus {
  job_id: number
  book_id: number
  step: string
  status: string
  progress: Record<string, unknown> | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
}

export interface AssertionResult {
  name: string
  category: string
  passed: boolean
  reasoning: string | null
  likely_cause: string | null
  suggestion: string | null
}

export interface EvalResult {
  section_id: number | null
  summary_id: number | null
  passed: number
  total: number
  eval_run_id: string | null
  assertions: AssertionResult[]
}

export interface BookEvalResult {
  book_id: number
  total_sections: number
  evaluated_sections: number
  overall_passed: number
  overall_total: number
  sections: EvalResult[]
}

export interface LibraryView {
  id: number
  name: string
  display_mode: string
  sort_field: string
  sort_direction: string
  filters: Record<string, unknown> | null
  table_columns: Record<string, unknown> | null
  position: number
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface SummaryComparison {
  summary_a: Summary
  summary_b: Summary
  concept_diff: Record<string, unknown> | null
}

// --- Reading Presets ---

export interface ReadingPreset {
  id: number
  name: string
  font_family: string
  font_size_px: number
  line_spacing: number
  content_width_px: number
  theme: string
  created_at: string
}

// --- Annotations ---

export interface Annotation {
  id: number
  content_type: string
  content_id: number
  text_start: number | null
  text_end: number | null
  selected_text: string | null
  note: string | null
  type: 'highlight' | 'note' | 'freeform'
  linked_annotation_id: number | null
  created_at: string
  updated_at: string
  // T18 — joined context from /annotations list.
  book_id?: number | null
  book_title?: string | null
  section_id?: number | null
  section_title?: string | null
}

// --- Concepts ---

export interface Concept {
  id: number
  book_id: number
  term: string
  definition: string
  user_edited: boolean
  created_at: string
  updated_at: string
}

export interface ConceptDetail extends Concept {
  section_appearances: SectionBrief[]
  related_concepts: Concept[]
  book_title: string
}

// --- AI Threads ---

export interface AIMessage {
  id: number
  thread_id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface AIThread {
  id: number
  book_id: number
  title: string
  messages: AIMessage[]
  created_at: string
  updated_at: string
}

export interface AIThreadListItem {
  id: number
  book_id: number
  title: string
  message_count: number
  last_message_preview: string | null
  created_at: string
  updated_at: string
}

// --- Search ---

export interface SearchHit {
  id: number
  book_id: number
  book_title: string
  snippet: string
  score: number
  title?: string
  section_title?: string | null
  term?: string
  note_snippet?: string | null
  selected_text?: string | null
}

export interface QuickSearchResults {
  books: SearchHit[]
  sections: SearchHit[]
  concepts: SearchHit[]
  annotations: SearchHit[]
}

export interface QuickSearchResponse {
  query: string
  results: QuickSearchResults
}

export interface SearchResultItem {
  source_type: string
  source_id: number
  book_id: number
  book_title: string
  section_title: string | null
  snippet: string
  score: number
  highlight: string
}

export interface RecentSearch {
  id: number
  query: string
  result_count: number | null
  created_at: string
}

// ──────────────────────────────────────────────────────────────────────
// Quiz (AI Comprehension Quiz, spec §9)
// ──────────────────────────────────────────────────────────────────────

export type QuizScopeMode = 'all_summaries' | 'specific_chapters'
export type QuizQuestionShape = 'mcq' | 'open' | 'spot_error'
export type QuizBloomLevel =
  | 'remember'
  | 'understand'
  | 'apply'
  | 'analyze'
  | 'evaluate'
  | 'create'
export type QuizSelfAssessment = 'got_it' | 'partial' | 'missed'
export type QuizSessionStatus = 'in_progress' | 'completed' | 'abandoned'

export interface QuizScope {
  mode: QuizScopeMode
  section_ids?: number[] | null
}

export interface QuizCitation {
  section_id: number
  section_title: string
  snippet: string
}

export interface QuizFeedback {
  correct: string
  missing: string
  actual: string
}

export interface QuizQuestion {
  id: number
  session_id: number | null
  book_id: number
  stem: string
  concept_label: string
  citation: QuizCitation
  shape: QuizQuestionShape
  bloom_level: QuizBloomLevel
  mcq_options?: string[] | null
  intended_error?: string | null
  error_explanation?: string | null
  user_answer?: string | null
  feedback?: QuizFeedback | null
  self_assessment?: QuizSelfAssessment | null
  override_note?: string | null
  explain_history: string[]
  skip_count: number
  discarded: boolean
  warm_up: boolean
  queue_hit?: boolean
  is_pregen: boolean
  is_stale: boolean
  created_at: string
  answered_at?: string | null
}

export interface QuizSessionTally {
  got_it: number
  partial: number
  missed: number
  skipped: number
  discarded: number
}

export interface QuizSessionListItem {
  id: number
  book_id: number
  scope: QuizScope
  theme: string | null
  status: QuizSessionStatus
  created_at: string
  ended_at: string | null
  question_count: number
  tally: QuizSessionTally
  is_warm_up_session: boolean
}

export interface QuizLifetimeTally {
  total_questions: number
  got_it: number
  partial: number
  missed: number
  session_count: number
  themes_summary?: string | null
}

export interface QuizSessionListResponse {
  sessions: QuizSessionListItem[]
  lifetime_tally: QuizLifetimeTally
}

export interface QuizSessionDetailResponse {
  session: QuizSessionListItem
  questions: QuizQuestion[]
}

export interface QuizStartResponse {
  session: QuizSessionListItem
  first_question: QuizQuestion
  warm_up_count: number
}

export interface QuizNextQuestionResponse {
  question: QuizQuestion
}

export interface QuizAnswerResponse {
  question: QuizQuestion
}

export interface QuizExplainResponse {
  explanation: string
  question: QuizQuestion
}

export interface QuizDiscardResponse {
  question: QuizQuestion
  replacement: QuizQuestion
}
