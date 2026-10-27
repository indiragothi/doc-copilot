import { useEffect, useState } from "react"
import { useOutletContext, useParams } from "react-router-dom"

import { ChatView } from "@/components/chat/chat-view"
import type { ChatMessage } from "@/lib/chat-types"
import { getThreadMessages } from "@/lib/threads"
import type { ChatLayoutContext } from "@/pages/chat-layout"

type Loaded = { threadId: string; messages: ChatMessage[] } | { threadId: string; error: string }

export default function ChatThreadPage() {
  const { threadId } = useParams<{ threadId: string }>()
  const { refreshThreads } = useOutletContext<ChatLayoutContext>()
  const [loaded, setLoaded] = useState<Loaded | null>(null)

  useEffect(() => {
    if (!threadId) return
    getThreadMessages(threadId)
      .then((messages) => setLoaded({ threadId, messages }))
      .catch((err: Error) => setLoaded({ threadId, error: err.message }))
  }, [threadId])

  // Ignore a result that belongs to the previously open thread.
  if (!loaded || loaded.threadId !== threadId) return null
  if ("error" in loaded) {
    return (
      <p role="alert" className="p-4 text-sm text-destructive">
        Could not load this conversation: {loaded.error}
      </p>
    )
  }
  return (
    <ChatView
      key={loaded.threadId}
      threadId={loaded.threadId}
      initialMessages={loaded.messages}
      onTurnFinished={refreshThreads}
    />
  )
}
