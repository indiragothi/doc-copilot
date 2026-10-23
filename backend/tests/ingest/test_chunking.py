from docling_core.types.doc import (
    DocItemLabel,
    DoclingDocument,
    TableCell,
    TableData,
)

from ingest.chunking import (
    CompactTableSerializer,
    build_chunker,
    chunk_document,
    join_row_cells,
    promote_item_headings,
    table_rows,
)


def make_table(rows: list[list[str]]) -> TableData:
    cells = [
        TableCell(
            text=text,
            start_row_offset_idx=r,
            end_row_offset_idx=r + 1,
            start_col_offset_idx=c,
            end_col_offset_idx=c + 1,
        )
        for r, row in enumerate(rows)
        for c, text in enumerate(row)
    ]
    return TableData(
        table_cells=cells, num_rows=len(rows), num_cols=max(len(r) for r in rows)
    )


def test_join_row_cells_reattaches_currency_and_percent_symbols():
    cells = ["Total net sales", "$", "416,161", "6", "%", "(4", ")", "%"]

    assert join_row_cells(cells) == "Total net sales | $416,161 | 6% | (4)%"


def test_table_rows_skips_blank_cells_and_keeps_row_order():
    table = DoclingDocument(name="t")
    item = table.add_table(
        data=make_table([["", "2025", ""], ["Europe", "", "111,032"], ["", "", ""]])
    )

    assert table_rows(item) == ["2025", "Europe | 111,032", ""]


def test_table_header_rows_before_first_amount_are_split_off():
    text = "Year Ended\n2025 | 2024\nRevenue | $60,922 | $26,974\nNet income | 29,760"

    header, body = CompactTableSerializer().get_header_and_body_lines(table_text=text)

    assert header == ["Year Ended\n", "2025 | 2024\n"]
    assert body == ["Revenue | $60,922 | $26,974", "Net income | 29,760"]


def test_item_text_becomes_heading_with_standard_title():
    doc = DoclingDocument(name="t")
    doc.add_text(label=DocItemLabel.TEXT, text="ITEM 1A. RIS K FACTORS")
    doc.add_text(label=DocItemLabel.TEXT, text="Item 1A.")  # table-of-contents cell
    doc.add_text(label=DocItemLabel.TEXT, text="See Item 1A for more detail.")

    promote_item_headings(doc)

    assert [h.text for h in doc.texts if h.label == DocItemLabel.SECTION_HEADER] == [
        "Item 1A. Risk Factors"
    ]
    assert len(doc.texts) == 3


def test_one_row_item_table_becomes_heading():
    doc = DoclingDocument(name="t")
    doc.add_table(data=make_table([["", ""], ["Item 7.", "MD&A"]]))
    doc.add_text(label=DocItemLabel.TEXT, text="Net sales increased.")

    promote_item_headings(doc)

    assert [h.text for h in doc.texts if h.label == DocItemLabel.SECTION_HEADER] == [
        "Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations"
    ]
    assert not doc.tables


def test_chunks_carry_section_and_stay_within_limit():
    doc = DoclingDocument(name="t")
    doc.add_text(label=DocItemLabel.TEXT, text="ITEM 1. BUSINESS")
    for i in range(120):
        doc.add_text(
            label=DocItemLabel.TEXT,
            text=f"Paragraph {i} describes the company's products and services in detail.",
        )
    doc.add_text(label=DocItemLabel.TEXT, text="ITEM 2. PROPERTIES")
    doc.add_text(label=DocItemLabel.TEXT, text="Headquarters are in Cupertino.")

    chunks = chunk_document(doc, build_chunker())

    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert len(chunks) > 2
    assert all(c.token_count <= 530 for c in chunks)
    assert chunks[0].section == "Item 1. Business"
    assert chunks[-1].section == "Item 2. Properties"
    assert chunks[-1].content.startswith("Item 2. Properties\n")
