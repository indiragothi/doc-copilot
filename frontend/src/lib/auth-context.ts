import type { Session } from "@supabase/supabase-js"
import { createContext, useContext } from "react"

export type AuthState = {
  session: Session | null
  // True until the initial session has been read from storage.
  loading: boolean
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const value = useContext(AuthContext)
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>")
  return value
}
