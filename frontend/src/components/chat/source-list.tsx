import { FileText } from "lucide-react"

import { citationLabel, type Citation } from "@/lib/chat-types"
import { cn } from "@/lib/utils"

type Props = {
  citations: Citation[]
  selectedId: string | null
  onSelect: (citation: Citation) => void
}

// The sources under an answer, so each one is readable without finding its [n] in the text.
export function SourceList({ citations, selectedId, onSelect }: Props) {
  return (
    <ul aria-label="Sources" className="mt-2 space-y-1">
      {citations.map((citation) => (
        <li key={citation.marker}>
          <button
            type="button"
            onClick={() => onSelect(citation)}
            className={cn(
              "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-xs hover:bg-background focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
              citation.chunk_id === selectedId && "bg-background font-medium",
            )}
          >
            <span className="font-medium tabular-nums">[{citation.marker}]</span>
            <FileText className="size-3.5 shrink-0 text-muted-foreground" />
            <span className="truncate">{citationLabel(citation)}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}
