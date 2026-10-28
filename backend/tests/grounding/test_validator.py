from datetime import date
from uuid import uuid4

from app.assistant.outputs import Citation, GroundedAnswer
from app.grounding.validator import validate_answer
from app.retrieval.models import SourcePassage

CONTENT = "Services net sales were $96.2 billion in 2025,\nup 13% from 2024."


def passage() -> SourcePassage:
    return SourcePassage(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        ticker="AAPL",
        form_type="10-K",
        fiscal_year=2025,
        filing_date=date(2025, 10, 31),
        section="Item 7.",
        page=None,
        content=CONTENT,
    )


def grounded(
    chunk, *, marker=1, quote="Services net sales were $96.2 billion", text=None
):
    return GroundedAnswer(
        answer=text or "Services grew to $96.2 billion [1].",
        citations=[Citation(marker=marker, chunk_id=chunk.chunk_id, quote=quote)],
    )


def test_valid_answer_has_no_violations():
    chunk = passage()

    assert validate_answer(grounded(chunk), {chunk.chunk_id: chunk}) == []


def test_quote_matches_across_whitespace_differences():
    chunk = passage()
    answer = grounded(chunk, quote="in 2025, up 13% from 2024")

    assert validate_answer(answer, {chunk.chunk_id: chunk}) == []


def test_citation_to_unretrieved_chunk_is_rejected():
    chunk = passage()

    violations = validate_answer(grounded(chunk), {})

    assert len(violations) == 1
    assert "not retrieved" in violations[0]


def test_fabricated_quote_is_rejected():
    chunk = passage()
    answer = grounded(chunk, quote="Services net sales were $120 billion")

    violations = validate_answer(answer, {chunk.chunk_id: chunk})

    assert len(violations) == 1
    assert "quote does not appear" in violations[0]


def test_answer_without_citations_is_rejected():
    answer = GroundedAnswer(answer="Services grew a lot.")

    assert any("no citations" in v for v in validate_answer(answer, {}))


def test_insufficient_evidence_may_have_no_citations():
    answer = GroundedAnswer(
        answer="The filings don't contain enough evidence.", insufficient_evidence=True
    )

    assert validate_answer(answer, {}) == []


def test_insufficient_evidence_with_citations_is_rejected():
    chunk = passage()
    answer = grounded(chunk).model_copy(update={"insufficient_evidence": True})

    violations = validate_answer(answer, {chunk.chunk_id: chunk})

    assert violations == ["An insufficient-evidence answer must not include citations."]


def test_empty_answer_is_rejected():
    for answer in (
        GroundedAnswer(answer="   ", insufficient_evidence=True),
        GroundedAnswer(answer=""),
    ):
        assert validate_answer(answer, {}) == ["The answer text is empty."]


def test_markers_must_be_numbered_from_one_without_gaps():
    chunk = passage()
    answer = grounded(chunk, marker=2, text="Services grew to $96.2 billion [2].")

    violations = validate_answer(answer, {chunk.chunk_id: chunk})

    assert violations == ["Citation markers must be numbered 1, 2, 3... without gaps."]


def test_marker_in_text_without_citation_is_rejected():
    chunk = passage()
    answer = grounded(chunk, text="Services grew [1] and iPhone shrank [2].")

    violations = validate_answer(answer, {chunk.chunk_id: chunk})

    assert violations == ["Marker [2] in the answer has no citation."]


def test_citation_never_referenced_in_text_is_rejected():
    chunk = passage()
    answer = grounded(chunk, text="Services grew.")

    violations = validate_answer(answer, {chunk.chunk_id: chunk})

    assert violations == ["Citation [1] is never referenced in the answer."]


def test_duplicate_markers_are_rejected():
    chunk = passage()
    answer = grounded(chunk)
    answer.citations.append(answer.citations[0])

    violations = validate_answer(answer, {chunk.chunk_id: chunk})

    assert violations == ["Marker [1] is used by more than one citation."]


def test_figure_missing_from_the_cited_chunk_is_rejected():
    chunk = passage()
    chunk = chunk.model_copy(update={"content": CONTENT + " Net sales were $416,161."})
    answer = grounded(chunk, text="Services grew; net sales were $420,000 [1].")

    violations = validate_answer(answer, {chunk.chunk_id: chunk})

    assert len(violations) == 1
    assert "420,000" in violations[0]
    assert "[1]" in violations[0]


def test_figure_present_in_the_cited_chunk_passes():
    chunk = passage().model_copy(
        update={"content": CONTENT + " Net sales were $416,161."}
    )
    answer = grounded(chunk, text="Net sales were $416161 [1].")

    assert validate_answer(answer, {chunk.chunk_id: chunk}) == []


def test_rounded_values_and_years_are_not_checked():
    chunk = passage()
    answer = grounded(
        chunk, text="In 2025 Services grew to about $96.2 billion, 13% [1]."
    )

    assert validate_answer(answer, {chunk.chunk_id: chunk}) == []


def test_segment_marked_as_a_calculation_is_not_checked():
    chunk = passage()
    answer = grounded(
        chunk,
        text="Services grew to $96.2 billion [1].\nMy calculation: +$12,345M [1].",
    )

    assert validate_answer(answer, {chunk.chunk_id: chunk}) == []


def test_figure_may_come_from_any_chunk_the_segment_cites():
    first = passage()
    second = passage().model_copy(update={"content": "Net sales were $416,161."})
    answer = GroundedAnswer(
        answer="Net sales were $416,161 while Services grew [1][2].",
        citations=[
            Citation(marker=1, chunk_id=first.chunk_id, quote="Services net sales"),
            Citation(marker=2, chunk_id=second.chunk_id, quote="Net sales were"),
        ],
    )

    retrieved = {first.chunk_id: first, second.chunk_id: second}
    assert validate_answer(answer, retrieved) == []


def test_lines_without_markers_are_not_checked():
    chunk = passage()
    answer = grounded(chunk, text="| Services | 999,999 |\nServices grew [1].")

    assert validate_answer(answer, {chunk.chunk_id: chunk}) == []


def test_difference_of_two_cited_figures_is_accepted():
    chunk = passage().model_copy(
        update={"content": CONTENT + " Net sales were $416,161 and $365,817."}
    )
    answer = grounded(chunk, text="Net sales rose by $50,344 [1].")

    assert validate_answer(answer, {chunk.chunk_id: chunk}) == []


def test_chunk_ids_quoted_in_the_text_are_not_figures():
    chunk = passage()
    answer = grounded(chunk, text="Services grew [1] (chunk 2046805f).")

    assert validate_answer(answer, {chunk.chunk_id: chunk}) == []


def test_grouped_markers_get_a_specific_violation():
    chunk = passage()
    answer = grounded(chunk, text="Services grew [1, 2].")

    violations = validate_answer(answer, {chunk.chunk_id: chunk})

    assert violations == [
        "Write each marker in its own brackets, e.g. [1][2], not [1, 2]."
    ]


def test_typographic_quotes_in_a_quote_still_match():
    chunk = passage().model_copy(
        update={"content": "Apple’s outsourcing partners — mostly in Asia."}
    )
    answer = grounded(
        chunk,
        quote="Apple's outsourcing partners - mostly in Asia.",
        text="Apple relies on partners [1].",
    )

    assert validate_answer(answer, {chunk.chunk_id: chunk}) == []


def test_quote_with_an_ellipsis_must_still_be_verbatim_in_each_part():
    chunk = passage()
    ok = grounded(
        chunk, quote="Services net sales were $96.2 billion ... up 13% from 2024."
    )
    bad = grounded(
        chunk, quote="Services net sales were $96.2 billion ... down 5% from 2024."
    )

    assert validate_answer(ok, {chunk.chunk_id: chunk}) == []
    assert len(validate_answer(bad, {chunk.chunk_id: chunk})) == 1


def test_chunk_id_in_the_text_gets_one_specific_violation():
    chunk = passage()
    answer = grounded(chunk, text=f"Services grew [{chunk.chunk_id}].")

    violations = validate_answer(answer, {chunk.chunk_id: chunk})

    assert len(violations) == 1
    assert "chunk id" in violations[0]
    assert str(chunk.chunk_id)[:8] in violations[0]
