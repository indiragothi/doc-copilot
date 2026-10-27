import ReactMarkdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

import { CitationChip } from "@/components/chat/citation-chip"
import { SourceList } from "@/components/chat/source-list"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
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
const CITE_HREF = "#cite-"

// "[2]" becomes a markdown link to "#cite-2" so the marker survives inside tables and bold text;
// the `a` renderer below turns those links into chips. Markers without a citation stay as text.
function linkMarkers(text: string, citations: Citation[]) {
  const known = new Set(citations.map((citation) => citation.marker))
  return text.replace(MARKER, (match, marker) =>
    known.has(Number(marker)) ? `[${marker}](${CITE_HREF}${marker})` : match,
  )
}

function answerComponents(
  citations: Citation[],
  selectedId: string | null,
  onSelect: (citation: Citation) => void,
): Components {
  const byMarker = new Map(citations.map((citation) => [citation.marker, citation]))
  return {
    a: ({ href, children }) => {
      const citation = href?.startsWith(CITE_HREF)
        ? byMarker.get(Number(href.slice(CITE_HREF.length)))
        : undefined
      if (!citation) return <>{children}</>
      return (
        <CitationChip
          citation={citation}
          active={citation.chunk_id === selectedId}
          onSelect={onSelect}
        />
      )
    },
    table: ({ children }) => <Table className="my-2 text-xs">{children}</Table>,
    thead: ({ children }) => <TableHeader>{children}</TableHeader>,
    tbody: ({ children }) => <TableBody>{children}</TableBody>,
    tr: ({ children }) => <TableRow>{children}</TableRow>,
    th: ({ children }) => <TableHead className="h-8 px-2">{children}</TableHead>,
    td: ({ children }) => <TableCell className="px-2 py-1">{children}</TableCell>,
    p: ({ children }) => <p className="my-1">{children}</p>,
    ul: ({ children }) => <ul className="my-1 list-disc pl-5">{children}</ul>,
    ol: ({ children }) => <ol className="my-1 list-decimal pl-5">{children}</ol>,
    h1: ({ children }) => <p className="mt-2 font-semibold">{children}</p>,
    h2: ({ children }) => <p className="mt-2 font-semibold">{children}</p>,
    h3: ({ children }) => <p className="mt-2 font-semibold">{children}</p>,
  }
}

export function MessageView({ message, selectedId, onSelectCitation }: Props) {
  const text = messageText(message)
  const isUser = message.role === "user"
  const citations = isUser ? [] : messageCitations(message)

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "min-w-0 rounded-lg px-3 py-2 text-sm",
          isUser
            ? "max-w-[75%] bg-primary text-primary-foreground"
            : "max-w-[95%] bg-muted",
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{text}</p>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={answerComponents(citations, selectedId, onSelectCitation)}
          >
            {linkMarkers(text, citations)}
          </ReactMarkdown>
        )}
        {!isUser && citations.length > 0 && (
          <SourceList
            citations={citations}
            selectedId={selectedId}
            onSelect={onSelectCitation}
          />
        )}
      </div>
    </div>
  )
}
