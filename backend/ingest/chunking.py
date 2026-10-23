"""Split a filing's DoclingDocument into token-bounded chunks ready for embedding."""

import re
from dataclasses import dataclass
from typing import Any, override

import tiktoken
from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer,
    ChunkingSerializerProvider,
)
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
from docling_core.transforms.serializer.base import (
    BaseDocSerializer,
    BaseTableSerializer,
    SerializationResult,
)
from docling_core.transforms.serializer.common import create_ser_result
from docling_core.types.doc import DoclingDocument, TableItem, TextItem

# Retrieval works best on passages far smaller than the embedding model's 32k context.
MAX_CHUNK_TOKENS = 512

# The Nemotron embedder's own tokenizer isn't published, so tokens are counted with
# cl100k_base. Counts differ by a few percent, which is irrelevant against a 32k limit.
_ENCODING = "cl100k_base"

# "Item 1A. Risk Factors" - the number and a title in one string. The bare "Item 1A."
# cells of the table of contents and running page headers don't match.
_ITEM_HEADING = re.compile(r"^item\s+(\d+[a-c]?)\.\s+\S.{0,150}$", re.IGNORECASE)

# Form 10-K item titles. Labels are built from these because the filings' own text varies
# in casing and some have stray spaces inside words ("RIS K FACTORS").
ITEM_TITLES = {
    "1": "Business",
    "1A": "Risk Factors",
    "1B": "Unresolved Staff Comments",
    "1C": "Cybersecurity",
    "2": "Properties",
    "3": "Legal Proceedings",
    "4": "Mine Safety Disclosures",
    "5": "Market for Registrant's Common Equity, Related Stockholder Matters and Issuer Purchases of Equity Securities",
    "6": "Selected Financial Data",
    "7": "Management's Discussion and Analysis of Financial Condition and Results of Operations",
    "7A": "Quantitative and Qualitative Disclosures About Market Risk",
    "8": "Financial Statements and Supplementary Data",
    "9": "Changes in and Disagreements with Accountants on Accounting and Financial Disclosure",
    "9A": "Controls and Procedures",
    "9B": "Other Information",
    "9C": "Disclosure Regarding Foreign Jurisdictions that Prevent Inspections",
    "10": "Directors, Executive Officers and Corporate Governance",
    "11": "Executive Compensation",
    "12": "Security Ownership of Certain Beneficial Owners and Management and Related Stockholder Matters",
    "13": "Certain Relationships and Related Transactions, and Director Independence",
    "14": "Principal Accountant Fees and Services",
    "15": "Exhibits and Financial Statement Schedules",
    "16": "Form 10-K Summary",
}
_AMOUNT = re.compile(r"\d{1,3},\d{3}|\$|%")
_MAX_REPEATED_HEADER_LINES = 4


@dataclass(frozen=True)
class FilingChunk:
    chunk_index: int
    section: str | None
    content: str
    token_count: int


class CompactTableSerializer(BaseTableSerializer):
    """One line per table row, `Label | $416,161 | 6%`.

    Docling's default writes a `row, column = value` sentence per grid cell, which turns
    the blank and merged cells of SEC tables into hundreds of tokens of noise.
    """

    @override
    def serialize(
        self,
        *,
        item: TableItem,
        doc_serializer: BaseDocSerializer,
        doc: DoclingDocument,
        **kwargs: Any,
    ) -> SerializationResult:
        parts = []
        caption = doc_serializer.serialize_captions(item=item, **kwargs)
        if caption.text:
            parts.append(caption.text)
        parts.extend(row for row in table_rows(item) if row)
        return create_ser_result(text="\n".join(parts), span_source=item)

    @override
    def get_header_and_body_lines(
        self, *, table_text: str, **kwargs: Any
    ) -> tuple[list[str], list[str]]:
        """Treat the rows before the first amount as column headers, repeated on every split."""
        lines = [line for line in table_text.split("\n") if line.strip()]
        first_amount = next(
            (i for i, line in enumerate(lines) if _AMOUNT.search(line)), len(lines)
        )
        header_end = min(first_amount, _MAX_REPEATED_HEADER_LINES)
        return [f"{line}\n" for line in lines[:header_end]], lines[header_end:]


def table_rows(table: TableItem) -> list[str]:
    cells_by_row: dict[int, list] = {}
    for cell in table.data.table_cells:
        cells_by_row.setdefault(cell.start_row_offset_idx, []).append(cell)

    rows = []
    for row_index in sorted(cells_by_row):
        cells = sorted(cells_by_row[row_index], key=lambda c: c.start_col_offset_idx)
        rows.append(join_row_cells([c.text.strip() for c in cells if c.text.strip()]))
    return rows


def join_row_cells(texts: list[str]) -> str:
    """Glue SEC's split-out symbols back on: `$`, `416,161` -> `$416,161`; `6`, `%` -> `6%`."""
    merged: list[str] = []
    for text in texts:
        if merged and (merged[-1] == "$" or text in {"%", ")"}):
            merged[-1] += text
        else:
            merged.append(text)
    return " | ".join(merged)


def promote_item_headings(doc: DoclingDocument) -> None:
    """Turn "Item 1A. Risk Factors" lines into real section headings.

    SEC filings are styled with bold text, not heading tags, so Docling finds no
    headings. Without them the chunker would merge across sections and could not
    label chunks. Amazon writes each item heading as a one-row table.
    """
    for item in [*doc.texts, *doc.tables]:
        text = _heading_text(item)
        if text is None:
            continue
        doc.insert_heading(sibling=item, text=text, level=1)
        doc.delete_items(node_items=[item])


def _heading_text(item: TextItem | TableItem) -> str | None:
    if isinstance(item, TableItem):
        rows = [row for row in table_rows(item) if row]
        if len(rows) != 1:
            return None
        text = rows[0].replace(" | ", " ")
    else:
        text = item.text.strip()
    match = _ITEM_HEADING.match(text)
    if match is None:
        return None
    number = match.group(1).upper()
    return f"Item {number}. {ITEM_TITLES.get(number, text)}"


def build_chunker() -> HybridChunker:
    tokenizer = OpenAITokenizer(
        tokenizer=tiktoken.get_encoding(_ENCODING), max_tokens=MAX_CHUNK_TOKENS
    )
    return HybridChunker(
        tokenizer=tokenizer,
        serializer_provider=_CompactSerializerProvider(),
    )


class _CompactSerializerProvider(ChunkingSerializerProvider):
    @override
    def get_serializer(self, doc: DoclingDocument) -> BaseDocSerializer:
        return ChunkingDocSerializer(doc=doc, table_serializer=CompactTableSerializer())


def chunk_document(doc: DoclingDocument, chunker: HybridChunker) -> list[FilingChunk]:
    promote_item_headings(doc)
    chunks = []
    for index, chunk in enumerate(chunker.chunk(doc)):
        content = chunker.contextualize(chunk)
        headings = chunk.meta.headings
        chunks.append(
            FilingChunk(
                chunk_index=index,
                section=headings[-1] if headings else None,
                content=content,
                token_count=chunker.tokenizer.count_tokens(content),
            )
        )
    return chunks
