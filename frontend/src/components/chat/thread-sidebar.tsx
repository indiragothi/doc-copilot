import { Plus, Trash2 } from "lucide-react"
import { NavLink } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { Thread } from "@/lib/threads"
import { supabase } from "@/lib/supabase"

type Props = {
  threads: Thread[]
  onNewChat: () => void
  onDelete: (thread: Thread) => void
  creating: boolean
  // Below md the sidebar is a drawer: hidden until opened, closed again after a choice.
  open: boolean
  onClose: () => void
}

export function ThreadSidebar({
  threads,
  onNewChat,
  onDelete,
  creating,
  open,
  onClose,
}: Props) {
  return (
    <>
      {open && (
        <button
          type="button"
          aria-label="Close menu"
          onClick={onClose}
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
        />
      )}
      <aside
        className={cn(
          "w-64 shrink-0 flex-col border-r bg-background max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-40 md:flex",
          open ? "flex" : "hidden",
        )}
      >
      <div className="p-3">
        <Button className="w-full" onClick={() => {
            onNewChat()
            onClose()
          }} disabled={creating}>
          <Plus /> New chat
        </Button>
      </div>
      <nav aria-label="Conversations" className="flex-1 overflow-y-auto px-2">
        {threads.length === 0 && (
          <p className="px-2 py-4 text-sm text-muted-foreground">No conversations yet.</p>
        )}
        {threads.map((thread) => (
          <div key={thread.id} className="group relative">
            <NavLink
              to={`/chat/${thread.id}`}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  "block truncate rounded-md py-2 pr-9 pl-2 text-sm hover:bg-muted",
                  isActive && "bg-muted font-medium",
                )
              }
            >
              {thread.title ?? "New chat"}
            </NavLink>
            {/* Hover-only on desktop; touch screens have no hover, so it stays visible below md. */}
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`Delete ${thread.title ?? "New chat"}`}
              onClick={() => onDelete(thread)}
              className="absolute top-1/2 right-1 -translate-y-1/2 text-muted-foreground hover:text-destructive md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100"
            >
              <Trash2 />
            </Button>
          </div>
        ))}
      </nav>
      <div className="p-3">
        <Button variant="outline" className="w-full" onClick={() => supabase.auth.signOut()}>
          Sign out
        </Button>
      </div>
      </aside>
    </>
  )
}
