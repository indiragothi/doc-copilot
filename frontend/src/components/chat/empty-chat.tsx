type Props = {
  onPick: (question: string) => void
}

// Questions the demo corpus (Apple 10-Ks, FY2021-2025) can answer, plus one it should refuse.
const SUGGESTIONS = [
  "How did Apple's revenue mix between iPhone, Services, Mac, iPad and Wearables change from 2021 to 2025?",
  "What do Apple's filings say about supplier concentration and reliance on third-party manufacturing?",
  "Do the filings prove that generative AI improved margins?",
]

export function EmptyChat({ onPick }: Props) {
  return (
    <div className="mx-auto mt-16 max-w-xl space-y-4 text-center">
      <div className="space-y-1">
        <h1 className="text-xl font-medium">Ask about the filings</h1>
        <p className="text-sm text-muted-foreground">
          Answers are drawn from Apple&apos;s 10-Ks (FY2021–2025) and cite the exact passage.
        </p>
      </div>
      <ul className="space-y-2">
        {SUGGESTIONS.map((question) => (
          <li key={question}>
            <button
              type="button"
              onClick={() => onPick(question)}
              className="w-full rounded-lg border p-3 text-left text-sm hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              {question}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
