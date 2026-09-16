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
    get_tools,
    normalize_arxiv_id,
    normalize_author,
)

DISCLOSURE_COLUMNS = {
    "arxiv_id", "url", "month", "field", "tag", "bucket", "second_reader",
    "quote", "tools_named", "vendors", "confidence",
}
EXAMINED_COLUMNS = {
    "month", "field", "papers_listed", "papers_examined", "papers_disclosing",
    "papers_denying", "is_partial",
}
AUTHOR_COLUMNS = {
    "author", "name", "first_paper_id", "first_paper_month", "first_paper_url",
    "last_paper_month", "n_papers", "n_papers_math_primary",
}
#: Multi-label series the tracker page draws one line per category from. Each category of
#: one of these shares the cell's denominator, so a category with no row for a month is a
#: hidden zero, not an undefined rate — and a consumer bucketing by quarter would silently
#: drop that whole quarter. `ai_ack_authors_band` and `ai_ack_novelty` are deliberately NOT
#: here: their denominator is the band's own papers, which can genuinely be zero.
DENSE_MULTI_LABEL = (
    "ai_ack_purpose", "ai_ack_vendor", "ai_ack_vendor_group",
    "author_adopted_group", "author_adopted_vendor", "author_adopted_vendor_group",
)
SECOND_READER = {"reread_confirmed", "pair_supported"}


@pytest.fixture(scope="module")
def tables():
    return get_all_tables()


def test_get_all_tables_returns_every_file(tables):
    assert set(tables) == set(FILES)
    for name, df in tables.items():
        assert isinstance(df, pd.DataFrame), name
        assert len(df) > 0, f"{name} is empty"


def test_disclosure_columns_and_values(tables):
    """`bucket` is checked against the published series rather than a hard-coded list:
    which buckets exist is itself a result of the classification run, so a list written
    here would have to be edited every version and would fail for the wrong reason."""
    df = tables["disclosures"]
    assert DISCLOSURE_COLUMNS.issubset(df.columns)
    monthly = tables["monthly"]
    published = set(monthly.loc[monthly["metric"] == "ai_ack_purpose", "category"])
    assert len(published) > 0, "no use-case series in the monthly file"
    # "" is a paper counted in the acknowledgement rate whose tags all sit in series that
    # did not clear the two-reader bar.
    assert set(df["bucket"]) <= published | {""}
    assert published <= set(df["bucket"]), "a published series with no per-paper rows"
    assert set(df["second_reader"]) == SECOND_READER, "every listed tag was backed one way"
    assert set(df["confidence"]) <= {"high", "medium", "low"}
    # the two research rungs are mutually exclusive per paper
    rungs = df[df["bucket"].isin(["substantial_research", "research_assistance"])]
    assert (rungs.groupby("arxiv_id")["bucket"].nunique() == 1).all()
    assert (df["quote"].str.len() > 0).all(), "every tag carries a quote"
    assert df["url"].str.startswith("https://arxiv.org/abs/").all()
    assert (df["month"] >= "2023-01").all()


def test_examined_columns_and_all_rows(tables):
    df = tables["examined"]
    assert EXAMINED_COLUMNS.issubset(df.columns)
    assert df["month"].min() == "2023-01"
    assert tables["papers"]["month"].min() == "2023-01"
    assert tables["monthly"]["period"].min() == "2023-01"
    # author history is NOT truncated: first papers reach back before 2023
    assert tables["authors"]["first_paper_month"].min() < "2000-01"
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
    assert len(get_disclosures(bucket="substantial_research")) > 0
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
    assert all(t["second_reader"] in SECOND_READER for t in paper["tags"])
    assert "confidence" not in paper, "confidence is per tag under v4, not per paper"
    assert len(paper["tools"]) == len(get_tools(arxiv_id=some))
    assert all(t["quote"] for t in paper["tools"]), "every tool carries its receipt"
    assert set(paper["buckets"]) == set(get_disclosures(arxiv_id=some)["bucket"]) - {""}
    assert get_paper("0000.00000") is None


def test_tools_table_is_the_receipt_behind_the_vendors(tables):
    """A paper's `vendors` recomputes from its tool rows: the non-empty, non-unnamed
    vendors, else `unnamed`. Every tool row has a verbatim sentence."""
    t, d = tables["tools"], tables["disclosures"]
    assert {"arxiv_id", "url", "month", "field", "tool", "vendor", "quote"} <= set(t.columns)
    assert (t["quote"].str.len() > 0).all()
    assert (t["tool"].str.len() > 0).all()
    assert set(t["arxiv_id"]) <= set(d["arxiv_id"])
    by_paper = t.groupby("arxiv_id")["vendor"].apply(
        lambda s: "; ".join(sorted({v for v in s if v and v != "unnamed"})) or "unnamed"
    )
    per_paper = d.drop_duplicates("arxiv_id").set_index("arxiv_id")["vendors"]
    for arxiv_id, vendors in per_paper.items():
        assert by_paper.get(arxiv_id, "unnamed") == vendors, arxiv_id
    # filters
    anthropic = get_tools(vendor="anthropic", month="2026")
    assert set(anthropic["vendor"]) == {"anthropic"} and anthropic["month"].str.startswith("2026").all()
    one = get_tools(tool=t.iloc[0]["tool"])
    assert set(one["tool"]) == {t.iloc[0]["tool"]}


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
    # A paper can be about AI and also state it used none; `papers_denying` counts it, so
    # the outcome column has to as well.
    denying = by_cell["outcome"].apply(lambda s: int((s == "denial").sum()))
    for row in ex[ex["field"] != "all"].itertuples():
        key = (row.month, row.field)
        assert int(listed[key]) == int(row.papers_listed), key
        assert int(examined[key]) == int(row.papers_examined), key
        assert int(disclosing[key]) == int(row.papers_disclosing), key
        assert int(denying[key]) == int(row.papers_denying), key
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


def test_multi_label_series_are_dense_in_every_cell(tables):
    """Every category of a shared-denominator series appears in every period that series
    covers.

    A consumer that buckets months into quarters keeps a quarter only when all three of
    its months are present FOR THAT CATEGORY. So a category emitted only in the months it
    was non-zero loses whole quarters from its line, with no error anywhere: the line just
    gets shorter. Publishing the zero row is what keeps a measured zero distinguishable
    from an absent one.
    """
    m = tables["monthly"]
    for metric in DENSE_MULTI_LABEL:
        rows = m[m["metric"] == metric]
        assert len(rows) > 0, f"{metric} is missing from the monthly series"
        for (field, population), cell in rows.groupby(["field", "population"]):
            periods = set(cell["period"])
            per_category = cell.groupby("category")["period"].apply(set)
            for category, got in per_category.items():
                missing = sorted(periods - got)
                assert not missing, (metric, field, population, category, missing[:3])
            # one denominator per period, shared by every category
            assert (cell.groupby("period")["denominator"].nunique() == 1).all(), (
                metric, field, population
            )


def test_use_case_and_vendor_series_agree_with_the_per_paper_tables(tables):
    """The chart lines and the per-paper rows count the same papers.

    `ai_ack_purpose` counts papers per bucket; `ai_ack_vendor` counts papers per vendor,
    where `unnamed` means the paper named no vendor at all and so has no row in `tools`.
    """
    m, d = tables["monthly"], tables["disclosures"]
    math_rows = m[(m["field"] == "math") & (m["population"] == "all") & ~m["is_partial"]]

    purpose = math_rows[math_rows["metric"] == "ai_ack_purpose"]
    per_bucket = purpose.groupby("category")["numerator"].sum()
    for bucket, published in per_bucket.items():
        listed = d.loc[d["bucket"] == bucket, "arxiv_id"].nunique()
        assert int(listed) == int(published), bucket

    vendor = math_rows[math_rows["metric"] == "ai_ack_vendor"]
    per_paper = d.drop_duplicates("arxiv_id").set_index("arxiv_id")["vendors"]
    for category, published in vendor.groupby("category")["numerator"].sum().items():
        listed = sum(
            1 for v in per_paper if category in [x.strip() for x in v.split(";") if x.strip()]
        )
        assert int(listed) == int(published), category


@pytest.mark.parametrize(
    ("cross", "row_of", "column_of"),
    [
        ("ai_ack_vendor_group", "ai_ack_vendor", "ai_ack_purpose"),
        ("author_adopted_vendor_group", "author_adopted_vendor", "author_adopted_group"),
    ],
)
def test_the_crosses_sit_inside_both_their_marginals(tables, cross, row_of, column_of):
    """`<vendor>:<bucket>` counts papers (or authors) that did BOTH, so it cannot exceed
    either marginal. It also does not sum to either: both dimensions are multi-label."""
    m = tables["monthly"]
    wanted = m[m["metric"].isin([cross, row_of, column_of])]
    key = ["field", "population", "period"]
    lookup = {
        (metric, *k): dict(zip(g["category"], g["numerator"], strict=True))
        for metric in (cross, row_of, column_of)
        for k, g in wanted[wanted["metric"] == metric].groupby(key)
    }
    checked = 0
    for (metric, *k), cells in lookup.items():
        if metric != cross:
            continue
        vendors = lookup.get((row_of, *k), {})
        buckets = lookup.get((column_of, *k), {})
        for category, n in cells.items():
            vendor, bucket = category.split(":", 1)
            assert n <= vendors.get(vendor, 0), (category, k)
            assert n <= buckets.get(bucket, 0), (category, k)
            checked += 1
    assert checked > 0, f"{cross} has no rows to check"
