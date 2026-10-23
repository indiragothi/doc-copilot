import { useState, type FormEvent } from "react"
import { Link, Navigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuth } from "@/lib/auth-context"
import { supabase } from "@/lib/supabase"

type Mode = "sign-in" | "sign-up"

const COPY = {
  "sign-in": {
    title: "Sign in",
    description: "Use your work email to continue.",
    submit: "Sign in",
    switchPrompt: "No account yet?",
    switchLabel: "Sign up",
    switchTo: "/signup",
  },
  "sign-up": {
    title: "Create account",
    description: "Sign up with your work email.",
    submit: "Sign up",
    switchPrompt: "Already have an account?",
    switchLabel: "Sign in",
    switchTo: "/login",
  },
} as const

export function AuthForm({ mode }: { mode: Mode }) {
  const { session } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const copy = COPY[mode]

  if (session) return <Navigate to="/chat" replace />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const credentials = {
      email: String(form.get("email")).trim(),
      password: String(form.get("password")),
    }

    setSubmitting(true)
    setError(null)
    setNotice(null)

    if (mode === "sign-in") {
      const { error } = await supabase.auth.signInWithPassword(credentials)
      if (error) setError(error.message)
    } else {
      const { data, error } = await supabase.auth.signUp(credentials)
      if (error) setError(error.message)
      // With email confirmation on, Supabase returns a user but no session yet.
      else if (!data.session) setNotice("Check your inbox to confirm your email, then sign in.")
    }
    setSubmitting(false)
  }

  return (
    <main className="flex min-h-svh items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>{copy.title}</CardTitle>
          <CardDescription>{copy.description}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" name="email" type="email" autoComplete="email" required />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete={mode === "sign-in" ? "current-password" : "new-password"}
                minLength={6}
                required
              />
            </div>
            {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
            {notice && <p role="status" className="text-sm text-muted-foreground">{notice}</p>}
            <Button type="submit" disabled={submitting}>
              {submitting ? "Please wait…" : copy.submit}
            </Button>
          </form>
          <p className="text-sm text-muted-foreground">
            {copy.switchPrompt}{" "}
            <Link to={copy.switchTo} className="underline underline-offset-4">
              {copy.switchLabel}
            </Link>
          </p>
        </CardContent>
      </Card>
    </main>
  )
}
