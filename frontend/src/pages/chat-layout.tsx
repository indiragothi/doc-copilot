import { useCallback, useEffect, useState } from "react"
import { Outlet, useNavigate } from "react-router-dom"

import { ThreadSidebar } from "@/components/chat/thread-sidebar"
import { createThread, listThreads, type Thread } from "@/lib/threads"

export type ChatLayoutContext = { refreshThreads: () => void }

export default function ChatLayout() {
  const navigate = useNavigate()
  const [threads, setThreads] = useState<Thread[]>([])
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  const refreshThreads = useCallback(() => {
    listThreads()
      .then(setThreads)
      .catch((err: Error) => setError(err.message))
  }, [])

  useEffect(refreshThreads, [refreshThreads])

  function newChat() {
    setCreating(true)
    createThread()
      .then((thread) => {
        refreshThreads()
        navigate(`/chat/${thread.id}`)
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setCreating(false))
  }

  return (
    <div className="flex h-svh">
      <ThreadSidebar threads={threads} onNewChat={newChat} creating={creating} />
      <main className="flex min-w-0 flex-1 flex-col">
        {error && (
          <p role="alert" className="p-3 text-sm text-destructive">
            {error}
          </p>
        )}
        <div className="min-h-0 flex-1">
          <Outlet context={{ refreshThreads } satisfies ChatLayoutContext} />
        </div>
      </main>
    </div>
  )
}
