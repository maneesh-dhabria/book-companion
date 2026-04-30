const BASE_URL = '/api/v1'

class ApiError extends Error {
  /** Raw detail from the server — array (FastAPI ValidationError),
   * string, or arbitrary structured object. ``Error.message`` is always
   * a sensible string regardless of the underlying shape so consumers
   * that read ``e.message`` (e.g. toast surfaces) get clean output. */
  public readonly detail: unknown

  constructor(
    public status: number,
    detail: unknown,
    public code: string = 'UNKNOWN',
  ) {
    const message = Array.isArray(detail)
      ? (detail as Array<{ msg?: string }>)
          .map((d) => (d?.msg ?? String(d)))
          .join('; ')
      : typeof detail === 'string'
        ? detail
        : detail === undefined || detail === null
          ? 'Request failed'
          : JSON.stringify(detail)
    super(message)
    this.name = 'ApiError'
    this.detail = detail
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: response.statusText, code: 'UNKNOWN' }))
    // Use ?? rather than || so a legitimate empty-string detail still surfaces
    // through the ApiError constructor's stringification path.
    throw new ApiError(response.status, body.detail ?? response.statusText, body.code)
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

  /** XHR-based upload that emits real progress (FR-F01). The fetch API
   * exposes no upstream progress events; XHR is the only browser primitive
   * that does. ``onProgress`` fires with whole-percent values 0..100 while
   * bytes are flushing; the returned Promise resolves with the parsed JSON
   * response and rejects with ApiError on non-2xx. Pass ``signal`` to support
   * cancel via AbortController. */
  uploadWithProgress<T>(
    url: string,
    file: File,
    onProgress: (pct: number) => void,
    options?: { fields?: Record<string, string>; signal?: AbortSignal },
  ): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      const formData = new FormData()
      formData.append('file', file)
      if (options?.fields) {
        for (const [k, v] of Object.entries(options.fields)) formData.append(k, v)
      }
      xhr.open('POST', `${BASE_URL}${url}`)
      xhr.upload.onprogress = (e: ProgressEvent) => {
        if (e.lengthComputable) onProgress(Math.round((100 * e.loaded) / e.total))
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(xhr.responseText ? (JSON.parse(xhr.responseText) as T) : (undefined as T))
          } catch (err) {
            reject(new ApiError(xhr.status, `Invalid JSON response: ${String(err)}`, 'PARSE'))
          }
          return
        }
        let detail: unknown = xhr.responseText
        try {
          const body = JSON.parse(xhr.responseText)
          detail = body?.detail ?? body
        } catch {
          // body wasn't JSON — leave as raw text
        }
        reject(new ApiError(xhr.status, detail))
      }
      xhr.onerror = () => reject(new ApiError(0, 'Network error', 'NETWORK'))
      xhr.onabort = () => reject(new ApiError(0, 'Cancelled', 'ABORT'))
      options?.signal?.addEventListener('abort', () => xhr.abort())
      xhr.send(formData)
    })
  },
}

export { ApiError }
