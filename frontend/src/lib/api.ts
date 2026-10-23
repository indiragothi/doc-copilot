import { env } from "@/lib/env"
import { createHttpClient } from "@/lib/http"
import { supabase } from "@/lib/supabase"

export async function getAccessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}

export const api = createHttpClient(env.apiBaseUrl, getAccessToken)
