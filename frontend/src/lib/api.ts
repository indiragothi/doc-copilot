import { env } from "@/lib/env"
import { createHttpClient } from "@/lib/http"
import { supabase } from "@/lib/supabase"

export const api = createHttpClient(env.apiBaseUrl, async () => {
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
})
