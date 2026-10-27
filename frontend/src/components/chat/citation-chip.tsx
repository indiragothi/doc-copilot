import { citationLabel, type Citation } from "@/lib/chat-types"
import { cn } from "@/lib/utils"

type Props = {
  citation: Citation
  active: boolean
  onSelect: (citation: Citation) => void
}

// Replaces an inline [n] marker; the full label sits in the title and aria-label.
export function CitationChip({ citation, active, onSelect }: Props) {
  const label = citationLabel(citation)
  return (
    <button
      type="button"
      onClick={() => onSelect(citation)}
      title={label}
      aria-label={`Source ${citation.marker}: ${label}`}
      aria-pressed={active}
      className={cn(
        "mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-md border px-1 align-baseline text-xs font-medium transition-colors hover:bg-primary hover:text-primary-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
        active && "bg-primary text-primary-foreground",
      )}
    >
      {citation.marker}
    </button>
  )
}
