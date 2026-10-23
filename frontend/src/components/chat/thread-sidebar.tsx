import { Plus } from "lucide-react"
import { NavLink } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { Thread } from "@/lib/threads"
import { supabase } from "@/lib/supabase"

type Props = {
  threads: Thread[]
  onNewChat: () => void
  creating: boolean
}

export function ThreadSidebar({ threads, onNewChat, creating }: Props) {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r">
      <div className="p-3">
        <Button className="w-full" onClick={onNewChat} disabled={creating}>
          <Plus /> New chat
        </Button>
      </div>
      <nav aria-label="Conversations" className="flex-1 overflow-y-auto px-2">
        {threads.length === 0 && (
          <p className="px-2 py-4 text-sm text-muted-foreground">No conversations yet.</p>
        )}
        {threads.map((thread) => (
          <NavLink
            key={thread.id}
            to={`/chat/${thread.id}`}
            className={({ isActive }) =>
              cn(
                "block truncate rounded-md px-2 py-2 text-sm hover:bg-muted",
                isActive && "bg-muted font-medium",
              )
            }
          >
            {thread.title ?? "New chat"}
          </NavLink>
        ))}
      </nav>
      <div className="p-3">
        <Button variant="outline" className="w-full" onClick={() => supabase.auth.signOut()}>
          Sign out
        </Button>
      </div>
    </aside>
  )
}
