import re
from collections.abc import Mapping
from uuid import UUID

from app.assistant.outputs import GroundedAnswer
from app.retrieval.models import SourcePassage

MARKER = re.compile(r"\[(\d+)\]")


def _normalize(text: str) -> str:
    return " ".join(text.split())


def validate_answer(
    answer: GroundedAnswer, retrieved: Mapping[UUID, SourcePassage]
) -> list[str]:
    """Return every grounding violation; an empty list means the answer may be shown."""
    violations: list[str] = []

    if not answer.citations and not answer.insufficient_evidence:
        violations.append(
            "The answer has no citations and does not say the evidence is insufficient."
        )

    markers = [citation.marker for citation in answer.citations]
    for marker in sorted({m for m in markers if markers.count(m) > 1}):
        violations.append(f"Marker [{marker}] is used by more than one citation.")

    for citation in answer.citations:
        passage = retrieved.get(citation.chunk_id)
        if passage is None:
            violations.append(
                f"Citation [{citation.marker}] points at chunk {citation.chunk_id}, "
                "which was not retrieved this turn."
            )
        elif _normalize(citation.quote) not in _normalize(passage.content):
            violations.append(
                f"Citation [{citation.marker}] quote does not appear in its chunk."
            )

    in_text = {int(m) for m in MARKER.findall(answer.answer)}
    cited = set(markers)
    for marker in sorted(in_text - cited):
        violations.append(f"Marker [{marker}] in the answer has no citation.")
    for marker in sorted(cited - in_text):
        violations.append(f"Citation [{marker}] is never referenced in the answer.")

    return violations
