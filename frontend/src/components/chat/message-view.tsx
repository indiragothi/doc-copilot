import { Fragment } from "react"

import { CitationChip } from "@/components/chat/citation-chip"
import { SourceList } from "@/components/chat/source-list"
import {
  messageCitations,
  messageText,
  type ChatMessage,
  type Citation,
} from "@/lib/chat-types"
import { cn } from "@/lib/utils"

type Props = {
  message: ChatMessage
  selectedId: string | null
  onSelectCitation: (citation: Citation) => void
}

const MARKER = /\[(\d+)\]/g

// Turns "[2]" into a chip when the answer carries a matching citation; other text stays as is.
function withChips(
  text: string,
  citations: Citation[],
  selectedId: string | null,
  onSelect: (citation: Citation) => void,
) {
  const byMarker = new Map(citations.map((citation) => [citation.marker, citation]))
  return text.split(MARKER).map((piece, index) => {
    // split() with a capture group alternates text, marker, text, marker, ...
    if (index % 2 === 0) return <Fragment key={index}>{piece}</Fragment>
    const citation = byMarker.get(Number(piece))
    if (!citation) return <Fragment key={index}>[{piece}]</Fragment>
    return (
      <CitationChip
        key={index}
        citation={citation}
        active={citation.chunk_id === selectedId}
        onSelect={onSelect}
      />
    )
  })
}

export function MessageView({ message, selectedId, onSelectCitation }: Props) {
  const text = messageText(message)
  const isUser = message.role === "user"
  const citations = isUser ? [] : messageCitations(message)

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[75%] rounded-lg px-3 py-2 text-sm",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted",
        )}
      >
        <p className="whitespace-pre-wrap">
          {isUser ? text : withChips(text, citations, selectedId, onSelectCitation)}
        </p>
        {!isUser && citations.length > 0 && (
          <SourceList
            citations={citations}
            selectedId={selectedId}
            onSelect={onSelectCitation}
          />
        )}
        {!isUser && citations.length === 0 && (
          <p className="mt-2 text-xs text-muted-foreground">
            No filing passages are cited for this answer.
          </p>
        )}
      </div>
    </div>
  )
}
