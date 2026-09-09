"""Smoke and consistency tests for arxiv_math_ai_data.

Verifies each public getter loads the committed data, returns a DataFrame with the
documented columns, and that the tables agree with each other: the per-paper
disclosure list counts to the `examined` file's `papers_disclosing` in every cell,
and every author key in the link tables exists in `authors`.
"""

from __future__ import annotations

import pandas as pd
import pytest

from arxiv_math_ai_data import (
    FILES,
    OUTCOMES,
    get_all_tables,
    get_author_fields,
    get_author_ids,
    get_author_papers,
    get_authors,
    get_disclosing_papers,
    get_disclosures,
    get_examined,
    get_first_paper,
    get_monthly,
    get_paper,
    get_papers,
    normalize_arxiv_id,
    normalize_author,
)

DISCLOSURE_COLUMNS = {
    "arxiv_id", "url", "month", "field", "tier", "tag", "bucket", "attribution",
    "verifier", "quote", "tools_named", "vendors", "confidence",
}
EXAMINED_COLUMNS = {
    "month", "field", "papers_listed", "papers_examined", "papers_disclosing",
    "papers_denying", "is_partial",
}
AUTHOR_COLUMNS = {
    "author", "name", "first_paper_id", "first_paper_month", "first_paper_url",
    "last_paper_month", "n_papers", "n_papers_math_primary",
}
BUCKETS = {"generated", "formalized", "research", "lit_review", "writing", "other", ""}


@pytest.fixture(scope="module")
def tables():
    return get_all_tables()


def test_get_all_tables_returns_every_file(tables):
    assert set(tables) == set(FILES)
    for name, df in tables.items():
        assert isinstance(df, pd.DataFrame), name
        assert len(df) > 0, f"{name} is empty"


def test_disclosure_columns_and_values(tables):
    df = tables["disclosures"]
    assert DISCLOSURE_COLUMNS.issubset(df.columns)
    assert set(df["bucket"]).issubset(BUCKETS)
    assert (df["quote"].str.len() > 0).all(), "every tag carries a quote"
    assert df["url"].str.startswith("https://arxiv.org/abs/").all()
    assert (df["month"] >= "2018-01").all()


def test_examined_columns_and_all_rows(tables):
    df = tables["examined"]
    assert EXAMINED_COLUMNS.issubset(df.columns)
    assert (df["papers_examined"] <= df["papers_listed"]).all()
    assert (df["papers_disclosing"] <= df["papers_examined"]).all()
    assert (df["field"] == "all").any()
    assert not df.duplicated(["month", "field"]).any()


def test_disclosures_count_to_the_examined_file_in_every_cell(tables):
    """The reconciliation the dataset rests on: ids listed == papers counted."""
    d, ex = tables["disclosures"], tables["examined"]
    per_field = d.groupby(["month", "field"])["arxiv_id"].nunique()
    per_month = d.groupby("month")["arxiv_id"].nunique()
    for row in ex.itertuples():
        got = per_month.get(row.month, 0) if row.field == "all" else per_field.get(
            (row.month, row.field), 0
        )
        assert int(got) == int(row.papers_disclosing), (row.month, row.field)


def test_month_and_field_filters():
    aug = get_disclosures(month="2026-08", field="math.CO")
    assert set(aug["month"]) <= {"2026-08"} and set(aug["field"]) <= {"math.CO"}
    year = get_disclosures(month="2025")
    assert year["month"].str.startswith("2025").all()
    span = get_disclosures(month=("2024-01", "2024-06"))
    assert span["month"].between("2024-01", "2024-06").all()
    assert len(get_disclosures(bucket="generated")) > 0
    assert set(get_disclosures(tag="writing_polish")["tag"]) == {"writing_polish"}


def test_disclosing_papers_is_one_row_per_paper():
    papers = get_disclosing_papers(month="2026-08")
    assert not papers["arxiv_id"].duplicated().any()
    tag_rows = get_disclosures(month="2026-08")
    assert len(papers) == tag_rows["arxiv_id"].nunique()
    assert {"tags", "buckets", "quotes"}.issubset(papers.columns)


def test_examined_field_argument():
    only_all = get_examined(field="all")
    assert set(only_all["field"]) == {"all"}
    everything = get_examined()
    assert len(everything) > len(only_all)


def test_author_tables_are_consistent(tables):
    authors, fields, papers, ids = (
        tables["authors"], tables["author_fields"], tables["author_papers"], tables["author_ids"]
    )
    assert AUTHOR_COLUMNS.issubset(authors.columns)
    assert not authors["author"].duplicated().any()
    keys = set(authors["author"])
    assert set(fields["author"]) <= keys
    assert set(papers["author"]) <= keys
    assert set(ids["author"]) <= keys
    assert (authors["first_paper_url"] == "https://arxiv.org/abs/" + authors["first_paper_id"]).all()
    assert (authors["n_papers_math_primary"] <= authors["n_papers"]).all()


def test_panel_filter():
    panel = get_authors(field="math.CO", panel=True)
    rest = get_authors(field="math.CO", panel=False)
    everyone = get_authors(field="math.CO")
    assert len(panel) > 0 and len(rest) > 0
    assert len(panel) + len(rest) == len(everyone)
    assert set(panel["author"]).isdisjoint(rest["author"])
    flags = get_author_fields(field="math.CO", panel=True)
    assert set(flags["author"]) == set(panel["author"])


def test_author_papers_and_first_paper_agree(tables):
    a = tables["authors"].iloc[0]
    papers = get_author_papers(a["author"])
    assert len(papers) == int(a["n_papers"])
    first = get_first_paper(a["author"])
    assert first == {
        "arxiv_id": a["first_paper_id"],
        "month": a["first_paper_month"],
        "url": a["first_paper_url"],
    }
    assert papers["month"].min() == first["month"]
    assert get_first_paper("nobody by this name") is None


def test_author_ids_filters(tables):
    with_orcid = get_author_ids(with_orcid=True)
    assert (with_orcid["orcid"] != "").all()
    assert with_orcid["orcid"].str.startswith("https://orcid.org/").all()
    some = tables["author_ids"].iloc[0]["author"]
    rows = get_author_ids(some)
    assert set(rows["author"]) == {some}
    assert list(rows["n_shared_papers"]) == sorted(rows["n_shared_papers"], reverse=True)


def test_normalize_author_matches_published_keys(tables):
    assert normalize_author("Paul Erdős") == "paul erdos"
    assert normalize_author("J.-P. Serre") == "j p serre"
    # every published key is already in normalised form
    sample = tables["authors"]["author"].head(2000)
    assert (sample.map(normalize_author) == sample).all()


def test_lookup_by_arxiv_id(tables):
    some = tables["disclosures"].iloc[0]["arxiv_id"]
    rows = get_disclosures(arxiv_id=some)
    assert set(rows["arxiv_id"]) == {some}
    assert len(rows) == int((tables["disclosures"]["arxiv_id"] == some).sum())
    # the same id in every spelling a user might paste
    for spelling in (f"arXiv:{some}", f"{some}v2", f"https://arxiv.org/abs/{some}",
                     f"https://arxiv.org/pdf/{some}v1"):
        assert normalize_arxiv_id(spelling) == some, spelling
        assert len(get_disclosures(arxiv_id=spelling)) == len(rows), spelling
    assert normalize_arxiv_id("math/9709222") == "math/9709222"
    two = get_disclosing_papers(arxiv_id=[some, "0000.00000"])
    assert list(two["arxiv_id"]) == [some]


def test_get_paper(tables):
    some = tables["disclosures"].iloc[0]["arxiv_id"]
    paper = get_paper(some)
    assert paper["arxiv_id"] == some
    assert paper["url"] == f"https://arxiv.org/abs/{some}"
    assert paper["outcome"] == "disclosure" and paper["examined"] is True
    assert len(paper["tags"]) == len(get_disclosures(arxiv_id=some))
    assert all(t["quote"] for t in paper["tags"])
    assert set(paper["buckets"]) == set(get_disclosures(arxiv_id=some)["bucket"]) - {""}
    assert get_paper("0000.00000") is None


def test_get_paper_answers_was_it_checked(tables):
    papers = tables["papers"]
    for outcome in ("no_hit", "no_disclosure", "not_examined", "denial"):
        some = papers[papers["outcome"] == outcome].iloc[0]["arxiv_id"]
        p = get_paper(some)
        assert p["outcome"] == outcome and "tags" not in p, outcome
        assert p["examined"] is (outcome != "not_examined")


def test_papers_table_reconciles_with_examined(tables):
    papers, ex = tables["papers"], tables["examined"]
    assert set(papers["outcome"]) <= set(OUTCOMES)
    assert not papers["arxiv_id"].duplicated().any()
    assert set(tables["disclosures"]["arxiv_id"]) == set(
        papers.loc[papers["outcome"] == "disclosure", "arxiv_id"]
    )
    by_cell = papers.groupby(["month", "field"])
    listed = by_cell.size()
    examined = by_cell["examined"].sum()
    disclosing = by_cell["outcome"].apply(lambda s: int((s == "disclosure").sum()))
    for row in ex[ex["field"] != "all"].itertuples():
        key = (row.month, row.field)
        assert int(listed[key]) == int(row.papers_listed), key
        assert int(examined[key]) == int(row.papers_examined), key
        assert int(disclosing[key]) == int(row.papers_disclosing), key
    assert len(get_papers(month="2026-08", field="all", outcome="disclosure")) == int(
        ex[(ex["month"] == "2026-08") & (ex["field"] == "all")].papers_disclosing.iloc[0]
    )


def test_monthly_series_loads_and_filters(tables):
    m = tables["monthly"]
    assert {"metric", "field", "period", "population", "category", "numerator",
            "denominator", "is_partial", "provenance"}.issubset(m.columns)
    assert not {"lean_proof_rate", "pages_per_paper"} & set(m["metric"])
    co = get_monthly("ai_ack_rate", field="math.CO")
    assert set(co["field"]) == {"math.CO"} and set(co["population"]) == {"all"}
    assert ((co["value"] >= 0) & (co["value"] <= 1)).all()
    everything = get_monthly("ai_ack_rate", field=None, population=None)
    assert {"all", "panel"} <= set(everything["population"])


def test_monthly_disclosure_rate_matches_the_examined_table():
    """The chart series and the row-level denominators are the same numbers."""
    rate = get_monthly("ai_ack_rate", field=None).set_index(["period", "field"])
    ex = get_examined().set_index(["month", "field"])
    for (period, field), row in rate.iterrows():
        cell = ex.loc[(period, "all" if field == "math" else field)]
        assert int(row["numerator"]) == int(cell["papers_disclosing"]), (period, field)
        assert int(row["denominator"]) == int(cell["papers_examined"]), (period, field)


def test_monthly_papers_total_matches_the_papers_table():
    total = get_monthly("papers_total", field=None)
    total = total[total["period"] <= get_papers()["month"].max()].set_index(["period", "field"])
    ex = get_examined().set_index(["month", "field"])
    for (period, field), row in total.iterrows():
        listed = ex.loc[(period, "all" if field == "math" else field), "papers_listed"]
        assert int(row["numerator"]) == int(listed), (period, field)


def test_monthly_tenure_is_rebuildable_from_the_author_tables():
    month = "2026-08"
    first = get_authors().set_index("author")["first_paper_month"]
    p = get_author_papers()
    p = p[p["is_math_primary"] & (p["month"] == month)].drop_duplicates("author")
    to_n = lambda m: int(m[:4]) * 12 + int(m[5:7])  # noqa: E731
    elapsed = p["month"].map(to_n) - p["author"].map(first).map(to_n)
    rebuilt = pd.cut(elapsed, [-1, 0, 60, 120, 10**6],
                     labels=["debut", "years_0_5", "years_5_10", "years_10_plus"]).value_counts()
    published = get_monthly("author_tenure", period=month).set_index("category")["numerator"]
    for bucket, n in rebuilt.items():
        assert int(n) == int(published[bucket]), bucket
