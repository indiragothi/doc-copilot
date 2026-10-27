import { X } from "lucide-react"
import { useEffect } from "react"

import { Button } from "@/components/ui/button"
import { citationLabel, formatFilingDate, type Citation } from "@/lib/chat-types"

type Props = {
  citation: Citation
  onClose: () => void
}

// The passage as stored, with the cited quote marked. Falls back to the plain excerpt
// if the quote isn't found (the backend validates it verbatim, so this is defensive only).
function Excerpt({ citation }: { citation: Citation }) {
  const start = citation.excerpt.indexOf(citation.quote)
  if (start === -1) return <>{citation.excerpt}</>
  const end = start + citation.quote.length
  return (
    <>
      {citation.excerpt.slice(0, start)}
      <mark className="rounded bg-yellow-200 px-0.5 text-foreground dark:bg-yellow-500/40">
        {citation.excerpt.slice(start, end)}
      </mark>
      {citation.excerpt.slice(end)}
    </>
  )
}

export function SourcePanel({ citation, onClose }: Props) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [onClose])

  return (
    <aside
      aria-label={`Source ${citation.marker}`}
      className="fixed inset-y-0 right-0 z-20 flex w-full max-w-md flex-col border-l bg-background shadow-lg lg:static lg:z-auto lg:w-96 lg:max-w-none lg:shrink-0 lg:shadow-none"
    >
      <header className="flex items-start justify-between gap-2 border-b p-3">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">Source [{citation.marker}]</p>
          <h2 className="text-sm font-medium">{citationLabel(citation)}</h2>
          <p className="text-xs text-muted-foreground">
            Filed {formatFilingDate(citation.filing_date)}
            {citation.page ? ` · Page ${citation.page}` : ""}
          </p>
        </div>
        <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close source">
          <X />
        </Button>
      </header>
      <div className="flex-1 overflow-y-auto p-3 text-sm leading-relaxed whitespace-pre-wrap">
        <Excerpt citation={citation} />
      </div>
    </aside>
  )
}
