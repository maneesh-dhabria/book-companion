import { apiClient } from './client'
import type {
  QuizAnswerResponse,
  QuizDiscardResponse,
  QuizExplainResponse,
  QuizLifetimeTally,
  QuizNextQuestionResponse,
  QuizQuestion,
  QuizScope,
  QuizSelfAssessment,
  QuizSessionDetailResponse,
  QuizSessionListItem,
  QuizSessionListResponse,
  QuizStartResponse,
} from '@/types'

export async function listSessions(bookId: number): Promise<QuizSessionListResponse> {
  return apiClient.get<QuizSessionListResponse>(`/books/${bookId}/quiz-sessions`)
}

export async function getLifetimeTally(bookId: number): Promise<QuizLifetimeTally> {
  return apiClient.get<QuizLifetimeTally>(`/books/${bookId}/quiz-sessions/lifetime-tally`)
}

export async function startSession(
  bookId: number,
  body: { scope: QuizScope; theme: string | null },
): Promise<QuizStartResponse> {
  return apiClient.post<QuizStartResponse>(`/books/${bookId}/quiz-sessions`, body)
}

export async function getSession(sessionId: number): Promise<QuizSessionDetailResponse> {
  return apiClient.get<QuizSessionDetailResponse>(`/quiz-sessions/${sessionId}`)
}

export async function nextQuestion(sessionId: number): Promise<QuizNextQuestionResponse> {
  return apiClient.post<QuizNextQuestionResponse>(`/quiz-sessions/${sessionId}/next-question`)
}

export async function submitAnswer(
  sessionId: number,
  questionId: number,
  answer: string,
): Promise<QuizAnswerResponse> {
  return apiClient.post<QuizAnswerResponse>(
    `/quiz-sessions/${sessionId}/questions/${questionId}/answer`,
    { answer },
  )
}

export async function recordSelfAssessment(
  sessionId: number,
  questionId: number,
  selfAssessment: QuizSelfAssessment,
): Promise<QuizQuestion> {
  return apiClient.patch<QuizQuestion>(
    `/quiz-sessions/${sessionId}/questions/${questionId}`,
    { self_assessment: selfAssessment },
  )
}

export async function skipQuestion(
  sessionId: number,
  questionId: number,
): Promise<QuizQuestion> {
  return apiClient.post<QuizQuestion>(
    `/quiz-sessions/${sessionId}/questions/${questionId}/skip`,
  )
}

export async function explainQuestion(
  sessionId: number,
  questionId: number,
): Promise<QuizExplainResponse> {
  return apiClient.post<QuizExplainResponse>(
    `/quiz-sessions/${sessionId}/questions/${questionId}/explain`,
  )
}

export async function overrideQuestion(
  sessionId: number,
  questionId: number,
  note: string,
): Promise<QuizQuestion> {
  return apiClient.post<QuizQuestion>(
    `/quiz-sessions/${sessionId}/questions/${questionId}/override`,
    { override_note: note },
  )
}

export async function discardQuestion(
  sessionId: number,
  questionId: number,
): Promise<QuizDiscardResponse> {
  return apiClient.post<QuizDiscardResponse>(
    `/quiz-sessions/${sessionId}/questions/${questionId}/discard`,
  )
}

export async function stopSession(sessionId: number): Promise<QuizSessionListItem> {
  return apiClient.post<QuizSessionListItem>(`/quiz-sessions/${sessionId}/stop`)
}
