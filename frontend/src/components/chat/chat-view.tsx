import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport } from "ai"
import { Send } from "lucide-react"
import { useCallback, useState } from "react"

import { EmptyChat } from "@/components/chat/empty-chat"
import { ErrorBanner } from "@/components/chat/error-banner"
import { MessageView } from "@/components/chat/message-view"
import { RunStatus, RunSummary } from "@/components/chat/run-status"
import { SourcePanel } from "@/components/chat/source-panel"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { getAccessToken } from "@/lib/api"
import { messageText, type ChatMessage, type Citation, type StatusStep } from "@/lib/chat-types"
import { env } from "@/lib/env"
import { supabase } from "@/lib/supabase"

type Props = {
  threadId: string
  initialMessages: ChatMessage[]
  onTurnFinished: () => void
}

// A step is reported when it starts and again when it ends, under the same id.
function upsertStep(steps: StatusStep[], step: StatusStep): StatusStep[] {
  const index = steps.findIndex((existing) => existing.id === step.id)
  if (index === -1) return [...steps, step]
  return steps.map((existing, i) => (i === index ? step : existing))
}

export function ChatView({ threadId, initialMessages, onTurnFinished }: Props) {
  const [input, setInput] = useState("")
  const [steps, setSteps] = useState<StatusStep[]>([])
  const [selected, setSelected] = useState<Citation | null>(null)
  const { messages, sendMessage, regenerate, status, error, clearError } = useChat<ChatMessage>({
    id: threadId,
    messages: initialMessages,
    transport: new DefaultChatTransport({
      api: `${env.apiBaseUrl}/chat/stream`,
      headers: async () => ({ Authorization: `Bearer ${await getAccessToken()}` }),
      // The backend identifies the thread by `threadId` and trusts only the last message.
      prepareSendMessagesRequest: ({ id, messages }) => ({
        body: { threadId: id, messages: messages.slice(-1) },
      }),
      fetch: async (input, init) => {
        const response = await fetch(input, init)
        // An expired or revoked session can't be retried; signing out sends the user to sign-in.
        if (response.status === 401) await supabase.auth.signOut()
        return response
      },
    }),
    onData: (part) => {
      if (part.type === "data-status") setSteps((current) => upsertStep(current, part.data))
    },
    onFinish: onTurnFinished,
  })
  const busy = status === "submitted" || status === "streaming"
  const last = messages.at(-1)
  // The verified answer is streamed only after the run ends, so text means the run is over.
  const answering = busy && last?.role === "assistant" && messageText(last) !== ""

  const ask = useCallback(
    (text: string) => {
      setSteps([])
      setSelected(null)
      void sendMessage({ text })
    },
    [sendMessage],
  )

  function submit(event: React.FormEvent) {
    event.preventDefault()
    const text = input.trim()
    if (!text || busy) return
    setInput("")
    ask(text)
  }

  function retry() {
    setSteps([])
    clearError()
    void regenerate()
  }

  return (
    <div className="flex h-full">
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {messages.length === 0 && <EmptyChat onPick={ask} />}
          {messages.map((message) =>
            // A failed run leaves an empty assistant message behind; there is nothing to show.
            message.role === "assistant" && messageText(message) === "" ? null : (
              <MessageView
                key={message.id}
                message={message}
                selectedId={selected?.chunk_id ?? null}
                onSelectCitation={setSelected}
              />
            ),
          )}
          {busy && !answering ? <RunStatus steps={steps} /> : <RunSummary steps={steps} />}
          {error && <ErrorBanner error={error} onRetry={retry} />}
        </div>
        <form onSubmit={submit} className="flex gap-2 border-t p-3">
          <Input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask about the filings…"
            aria-label="Message"
          />
          <Button type="submit" disabled={busy || !input.trim()}>
            <Send /> Send
          </Button>
        </form>
      </div>
      {selected && <SourcePanel citation={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
