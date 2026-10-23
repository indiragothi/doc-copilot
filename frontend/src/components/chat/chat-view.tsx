import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport, type UIMessage } from "ai"
import { LoaderCircle, Send } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { getAccessToken } from "@/lib/api"
import { env } from "@/lib/env"
import { cn } from "@/lib/utils"

type Props = {
  threadId: string
  initialMessages: UIMessage[]
  onTurnFinished: () => void
}

export function ChatView({ threadId, initialMessages, onTurnFinished }: Props) {
  const [input, setInput] = useState("")
  const { messages, sendMessage, status, error } = useChat({
    id: threadId,
    messages: initialMessages,
    transport: new DefaultChatTransport({
      api: `${env.apiBaseUrl}/chat/stream`,
      headers: async () => ({ Authorization: `Bearer ${await getAccessToken()}` }),
      // The backend identifies the thread by `threadId` and trusts only the last message.
      prepareSendMessagesRequest: ({ id, messages }) => ({
        body: { threadId: id, messages: messages.slice(-1) },
      }),
    }),
    onFinish: onTurnFinished,
  })
  const busy = status === "submitted" || status === "streaming"

  function submit(event: React.FormEvent) {
    event.preventDefault()
    const text = input.trim()
    if (!text || busy) return
    setInput("")
    void sendMessage({ text })
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <p className="mt-16 text-center text-sm text-muted-foreground">
            Ask a question about the filings to get started.
          </p>
        )}
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}
          >
            <p
              className={cn(
                "max-w-[75%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm",
                message.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted",
              )}
            >
              {message.parts.map((part) => (part.type === "text" ? part.text : "")).join("")}
            </p>
          </div>
        ))}
        {busy && (
          <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
            <LoaderCircle className="size-4 animate-spin" />
            {status === "submitted" ? "Thinking…" : "Responding…"}
          </p>
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            Something went wrong: {error.message}
          </p>
        )}
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
  )
}
