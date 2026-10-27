import { Check, LoaderCircle, TriangleAlert } from "lucide-react"

import type { StatusStep } from "@/lib/chat-types"
import { cn } from "@/lib/utils"

type Props = {
  steps: StatusStep[]
}

// Between steps the model is reading results or drafting, which emits no event of its own.
function placeholder(steps: StatusStep[]): string {
  return steps.length === 0 ? "Understanding your question…" : "Analyzing passages…"
}

export function RunStatus({ steps }: Props) {
  const idle = !steps.some((step) => step.state === "running")
  return (
    <div role="status" aria-live="polite" className="space-y-1.5 text-sm">
      {steps.map((step) => (
        <div key={step.id} className="flex items-start gap-2">
          <StepIcon state={step.state} />
          <div className="min-w-0">
            <span className={cn(step.state === "running" && "font-medium")}>{step.label}</span>
            {step.detail && (
              <span className="ml-2 text-muted-foreground">{step.detail}</span>
            )}
          </div>
        </div>
      ))}
      {idle && (
        <div className="flex items-center gap-2 text-muted-foreground">
          <LoaderCircle className="size-4 animate-spin" />
          {placeholder(steps)}
        </div>
      )}
    </div>
  )
}

function StepIcon({ state }: { state: StatusStep["state"] }) {
  if (state === "running") return <LoaderCircle className="mt-0.5 size-4 shrink-0 animate-spin" />
  if (state === "failed")
    return <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" />
  return <Check className="mt-0.5 size-4 shrink-0 text-emerald-600" />
}

// What the last run leaves behind under the answer.
export function RunSummary({ steps }: { steps: StatusStep[] }) {
  const searches = steps.filter((step) => step.label === "Searching filings").length
  const reads = steps.filter((step) => step.label.startsWith("Reading")).length
  if (searches + reads === 0) return null
  const parts = [
    searches > 0 && `${searches} ${searches === 1 ? "search" : "searches"}`,
    reads > 0 && `${reads} ${reads === 1 ? "read" : "reads"}`,
  ].filter(Boolean)
  return <p className="text-xs text-muted-foreground">{parts.join(" · ")}</p>
}
