import re
from collections.abc import Mapping
from uuid import UUID

from app.assistant.outputs import GroundedAnswer
from app.retrieval.models import SourcePassage

MARKER = re.compile(r"\[(\d+)\]")
# A number token, whole: "109,158", "96.2", "2025". The lookbehind stops it matching mid-number.
NUMBER = re.compile(r"(?<![\d,.])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
# Chunk ids quoted in the text ("2046805f") contain digits but are not figures.
HEX_ID = re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,}\b")
SEGMENT_BREAK = re.compile(r"\n+|(?<=[.!?])\s+")
# Percentage-point changes and the like are not in any chunk, so a segment that says it is a
# calculation is not checked. Plain differences and sums of cited figures pass on their own.
CALCULATION = re.compile(
    r"calculat|computed|derived|approximately|roughly|estimate|\bpp\b|percentage point",
    re.IGNORECASE,
)


# Models often straighten typographic quotes and dashes when copying a quote.
TYPOGRAPHY = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})
# "[1, 2]" is one bracket holding several markers; each marker must have its own brackets.
GROUPED_MARKERS = re.compile(r"\[\d+(?:\s*[,;]\s*\d+)+\]")


# A quote may skip text with an ellipsis; each part between ellipses must still be verbatim.
ELLIPSIS = re.compile(r"\s*(?:\.{3}|…)\s*")


def _quote_in_chunk(quote: str, content: str) -> bool:
    chunk = _normalize(content)
    parts = [_normalize(part) for part in ELLIPSIS.split(quote)]
    return all(part in chunk for part in parts if part)


def _normalize(text: str) -> str:
    return " ".join(text.translate(TYPOGRAPHY).split())


def _is_reported_figure(token: str) -> bool:
    """Exact table figures like 109,158 or 416161. Rounded values ($96.2 billion) and
    years are not checked: they legitimately differ from the filing's text."""
    return "," in token or len(token.split(".")[0]) >= 5


def _is_derived(figure: float, evidence: set[float]) -> bool:
    """A difference or sum of two figures from the cited chunks (e.g. year-on-year growth)."""
    return any(
        abs(a - b) == figure or a + b == figure for a in evidence for b in evidence
    )


def _unsupported_figures(
    answer: GroundedAnswer, retrieved: Mapping[UUID, SourcePassage]
) -> list[str]:
    """Figures stated next to a [n] marker that appear in none of the chunks that marker cites."""
    chunks = {
        c.marker: {
            t.replace(",", "") for t in NUMBER.findall(retrieved[c.chunk_id].content)
        }
        for c in answer.citations
        if c.chunk_id in retrieved
    }
    violations = []
    for segment in SEGMENT_BREAK.split(answer.answer):
        markers = [int(m) for m in MARKER.findall(segment)]
        if not markers or CALCULATION.search(segment):
            continue
        evidence = set().union(*(chunks.get(m, set()) for m in markers))
        numbers = {float(t) for t in evidence}
        text = HEX_ID.sub("", MARKER.sub("", segment))
        missing = [
            token
            for token in dict.fromkeys(NUMBER.findall(text))
            if _is_reported_figure(token)
            and token.replace(",", "") not in evidence
            and not _is_derived(float(token.replace(",", "")), numbers)
        ]
        if missing:
            cited = "".join(f"[{m}]" for m in markers)
            violations.append(
                f'{", ".join(missing)} (in "{segment.strip()[:80]}") does not appear in '
                f"the chunk(s) cited as {cited}. Cite the chunk that contains it, or say "
                "the figure is your own calculation."
            )
    return violations


def validate_answer(
    answer: GroundedAnswer, retrieved: Mapping[UUID, SourcePassage]
) -> list[str]:
    """Return every grounding violation; an empty list means the answer may be shown."""
    if not answer.answer.strip():
        return ["The answer text is empty."]

    # Declining to answer is the one case that needs no evidence, and must claim none.
    if answer.insufficient_evidence:
        if answer.citations:
            return ["An insufficient-evidence answer must not include citations."]
        return []

    if not answer.citations:
        return [
            "The answer has no citations and does not say the evidence is insufficient."
        ]

    violations: list[str] = []
    markers = [citation.marker for citation in answer.citations]
    duplicates = sorted({m for m in markers if markers.count(m) > 1})
    for marker in duplicates:
        violations.append(f"Marker [{marker}] is used by more than one citation.")
    if not duplicates and sorted(markers) != list(range(1, len(markers) + 1)):
        violations.append("Citation markers must be numbered 1, 2, 3... without gaps.")

    for citation in answer.citations:
        passage = retrieved.get(citation.chunk_id)
        if passage is None:
            violations.append(
                f"Citation [{citation.marker}] points at chunk {citation.chunk_id}, "
                "which was not retrieved this turn."
            )
        elif not _quote_in_chunk(citation.quote, passage.content):
            violations.append(
                f"Citation [{citation.marker}] quote does not appear in its chunk."
            )

    grouped = GROUPED_MARKERS.findall(answer.answer)
    if grouped:
        violations.append(
            f"Write each marker in its own brackets, e.g. [1][2], not {grouped[0]}."
        )

    in_text = {int(m) for m in MARKER.findall(answer.answer)}
    cited = set(markers)
    for marker in sorted(in_text - cited):
        violations.append(f"Marker [{marker}] in the answer has no citation.")
    for marker in sorted(cited - in_text if not grouped else set()):
        violations.append(f"Citation [{marker}] is never referenced in the answer.")

    if not violations:
        violations.extend(_unsupported_figures(answer, retrieved))
    return violations
