import type { Session } from "@supabase/supabase-js"
import { useEffect, useState, type ReactNode } from "react"

import { AuthContext } from "@/lib/auth-context"
import { supabase } from "@/lib/supabase"

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // INITIAL_SESSION fires once on subscribe, then again on sign-in/out and token refresh.
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
      setLoading(false)
    })
    return () => data.subscription.unsubscribe()
  }, [])

  return <AuthContext value={{ session, loading }}>{children}</AuthContext>
}
