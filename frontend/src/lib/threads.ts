import { api } from "@/lib/api"
import type { ChatMessage } from "@/lib/chat-types"

export type Thread = {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export const listThreads = () => api.get<Thread[]>("/chat/threads")

export const createThread = () => api.post<Thread>("/chat/threads")

export const getThreadMessages = (threadId: string) =>
  api.get<ChatMessage[]>(`/chat/threads/${threadId}/messages`)
