import { TriangleAlert } from "lucide-react"

import { Button } from "@/components/ui/button"

type Props = {
  error: Error
  onRetry: () => void
}

// fetch() rejects with a TypeError when no response arrived (offline, CORS, DNS).
const NETWORK_MESSAGES = ["failed to fetch", "networkerror", "load failed"]

// The transport reports non-2xx responses as the raw body, which is FastAPI's {"detail": "..."}.
function detailOf(message: string): string {
  try {
    const body: unknown = JSON.parse(message)
    if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
      return body.detail
    }
  } catch {
    // Not JSON: a stream error event or a plain message.
  }
  return message
}

function describe(error: Error): string {
  const lower = error.message.toLowerCase()
  if (NETWORK_MESSAGES.some((text) => lower.includes(text))) {
    return "Can't reach the server. Check your connection and try again."
  }
  return detailOf(error.message)
}

export function ErrorBanner({ error, onRetry }: Props) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm"
    >
      <TriangleAlert className="mt-0.5 size-4 shrink-0 text-destructive" />
      <p className="min-w-0 flex-1">{describe(error)}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        Try again
      </Button>
    </div>
  )
}
