const DEFAULT_TIMEOUT_MS = 30_000

export class ApiError extends Error {
  status: number | null
  // True when no HTTP response arrived at all (offline, CORS, DNS, timeout).
  isNetworkError: boolean

  constructor(message: string, status: number | null, isNetworkError = false) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.isNetworkError = isNetworkError
  }
}

type GetToken = () => Promise<string | null>

export function createHttpClient(baseUrl: string, getToken: GetToken) {
  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers: Record<string, string> = {}
    const token = await getToken()
    if (token) headers.Authorization = `Bearer ${token}`
    if (body !== undefined) headers["Content-Type"] = "application/json"

    let response: Response
    try {
      response = await fetch(`${baseUrl}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
      })
    } catch (error) {
      const timedOut = error instanceof DOMException && error.name === "TimeoutError"
      throw new ApiError(timedOut ? "Request timed out" : "Network error", null, true)
    }

    if (!response.ok) {
      throw new ApiError(await errorMessage(response), response.status)
    }
    return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
  }

  return {
    get: <T>(path: string) => request<T>("GET", path),
    post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
    put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
    patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
    delete: <T>(path: string) => request<T>("DELETE", path),
  }
}

// FastAPI errors look like {"detail": "..."}; fall back to the status text.
async function errorMessage(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json()
    if (data && typeof data === "object" && "detail" in data && typeof data.detail === "string") {
      return data.detail
    }
  } catch {
    // Body wasn't JSON.
  }
  return response.statusText || `Request failed (${response.status})`
}
