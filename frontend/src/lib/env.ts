const required = [
  "VITE_API_BASE_URL",
  "VITE_SUPABASE_URL",
  "VITE_SUPABASE_ANON_KEY",
] as const

const missing = required.filter((name) => !import.meta.env[name])
if (missing.length > 0) {
  throw new Error(`Missing required env vars: ${missing.join(", ")}`)
}

export const env = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL.replace(/\/+$/, ""),
  supabaseUrl: import.meta.env.VITE_SUPABASE_URL,
  supabaseAnonKey: import.meta.env.VITE_SUPABASE_ANON_KEY,
}
