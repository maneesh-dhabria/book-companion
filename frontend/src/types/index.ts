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
}

export interface SectionBrief {
  id: number
  title: string
  order_index: number
  section_type: string
  content_token_count: number | null
  has_summary: boolean
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
}

export interface Section {
  id: number
  book_id: number
  title: string
  order_index: number
  section_type: string
  content_token_count: number | null
  content_md: string | null
  default_summary: SummaryBrief | null
  summary_count: number
  annotation_count: number
  has_summary: boolean
}

export interface SummaryBrief {
  id: number
  preset_name: string | null
  model_used: string
  summary_char_count: number
  created_at: string
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
