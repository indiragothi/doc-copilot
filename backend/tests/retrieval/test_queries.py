from sqlalchemy.dialects import postgresql

from app.retrieval.models import SearchFilters
from app.retrieval.queries import build_tsquery, keyword_statement, semantic_statement


def sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_tsquery_ors_distinct_lowercased_words():
    assert (
        build_tsquery("Apple's iPhone sales, iPhone!") == "apple | s | iphone | sales"
    )


def test_tsquery_of_punctuation_only_is_empty():
    assert build_tsquery("?!  --") == ""


def test_tsquery_strips_syntax_characters():
    assert build_tsquery("a'; drop table & (x) | !y") == "a | drop | table | x | y"


def test_semantic_statement_orders_by_cosine_distance_with_limit():
    compiled = sql(semantic_statement([0.1] * 3, 50, SearchFilters()))

    assert "<=>" in compiled
    assert "LIMIT" in compiled
    assert "ticker" not in compiled


def test_keyword_statement_matches_and_ranks_full_text():
    compiled = sql(keyword_statement("revenue | mix", 50, SearchFilters()))

    assert "@@" in compiled
    assert "ts_rank_cd" in compiled
    assert "LIMIT" in compiled


def test_filters_reach_both_statements():
    filters = SearchFilters(ticker="AAPL", fiscal_year=2025, form_type="10-K")

    for compiled in (
        sql(semantic_statement([0.1] * 3, 5, filters)),
        sql(keyword_statement("x", 5, filters)),
    ):
        assert "source_documents.ticker =" in compiled
        assert "source_documents.fiscal_year =" in compiled
        assert "source_documents.form_type =" in compiled
