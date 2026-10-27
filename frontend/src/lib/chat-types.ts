import type { UIMessage } from "ai"

export type Citation = {
  marker: number
  chunk_id: string
  quote: string
  excerpt: string
  ticker: string
  form_type: string
  fiscal_year: number
  filing_date: string
  section: string | null
  page: number | null
}

export type StatusStep = {
  id: string
  label: string
  detail: string | null
  state: "running" | "done" | "failed"
}

export type ChatMessage = UIMessage<unknown, { citation: Citation; status: StatusStep }>

export function messageText(message: ChatMessage): string {
  return message.parts.map((part) => (part.type === "text" ? part.text : "")).join("")
}

export function messageCitations(message: ChatMessage): Citation[] {
  return message.parts.flatMap((part) => (part.type === "data-citation" ? [part.data] : []))
}

// "Item 7." -> "Item 7"; the stored section keeps the filing's trailing period.
export function citationLabel(citation: Citation): string {
  const section = citation.section?.replace(/\.$/, "")
  return [citation.ticker, `${citation.form_type} FY${citation.fiscal_year}`, section]
    .filter(Boolean)
    .join(" · ")
}

export function formatFilingDate(isoDate: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(
    new Date(`${isoDate}T00:00:00`),
  )
}
