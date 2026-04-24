const BASE_URL = '/api/v1'

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public code: string = 'UNKNOWN',
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText, code: 'UNKNOWN' }))
    throw new ApiError(response.status, body.detail || response.statusText, body.code)
  }
  if (response.status === 204) return undefined as T
  return response.json()
}

export const apiClient = {
  async get<T>(
    url: string,
    params?: Record<string, string | number | boolean | undefined>,
    options?: { signal?: AbortSignal },
  ): Promise<T> {
    const searchParams = new URLSearchParams()
    if (params) {
      for (const [key, value] of Object.entries(params)) {
        if (value !== undefined) searchParams.set(key, String(value))
      }
    }
    const query = searchParams.toString()
    const fullUrl = `${BASE_URL}${url}${query ? `?${query}` : ''}`
    const response = await fetch(fullUrl, { signal: options?.signal })
    return handleResponse<T>(response)
  },

  async post<T>(url: string, body?: unknown): Promise<T> {
    const response = await fetch(`${BASE_URL}${url}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(response)
  },

  async patch<T>(url: string, body: unknown): Promise<T> {
    const response = await fetch(`${BASE_URL}${url}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return handleResponse<T>(response)
  },

  async put<T>(url: string, body?: unknown): Promise<T> {
    const response = await fetch(`${BASE_URL}${url}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(response)
  },

  async delete(url: string): Promise<void> {
    const response = await fetch(`${BASE_URL}${url}`, { method: 'DELETE' })
    return handleResponse<void>(response)
  },

  async upload<T>(url: string, file: File, fields?: Record<string, string>): Promise<T> {
    const formData = new FormData()
    formData.append('file', file)
    if (fields) {
      for (const [key, value] of Object.entries(fields)) {
        formData.append(key, value)
      }
    }
    const response = await fetch(`${BASE_URL}${url}`, {
      method: 'POST',
      body: formData,
    })
    return handleResponse<T>(response)
  },
}

export { ApiError }
