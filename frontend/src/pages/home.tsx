import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { supabase } from "@/lib/supabase"

type Me = { id: string; email: string | null }

// Placeholder until the chat shell lands in Phase 3; it proves the token reaches the backend.
export default function HomePage() {
  const [me, setMe] = useState<Me | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .get<Me>("/me")
      .then(setMe)
      .catch((err: Error) => setError(err.message))
  }, [])

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-4 p-4">
      <h1 className="text-xl font-medium">Document Copilot</h1>
      {me && <p className="text-sm">Backend sees you as {me.email} ({me.id})</p>}
      {error && <p role="alert" className="text-sm text-destructive">Backend error: {error}</p>}
      <Button variant="outline" onClick={() => supabase.auth.signOut()}>
        Sign out
      </Button>
    </main>
  )
}
