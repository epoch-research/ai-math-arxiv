"""AI use in mathematics research, measured on arXiv — the public dataset.

Two datasets, seven tables, read from the CSV files in `data/`:

  PAPERS -> AI-USE DISCLOSURES
    disclosures    one row per (paper, use tag) with the verbatim quote behind the tag
    examined       per (month, field): papers listed, examined, disclosing, denying
    papers         one row per listed paper with its outcome (was it checked, and what
                   came of it): not_examined / no_hit / no_disclosure / subject_matter /
                   denial / disclosure / unresolved

  AUTHORS
    authors        one row per author key: display name, first paper, paper counts
    author_fields  one row per (author, math field): in-field counts and panel flag
    author_papers  one row per (author, paper)
    author_ids     crosswalk to OpenAlex author ids and ORCIDs

Usage:

    from arxiv_math_ai_data import get_disclosures, get_authors

    get_disclosures(month="2026-08", field="math.CO")     # tag rows, with quotes
    get_disclosing_papers(month="2026")                    # one row per paper
    get_authors(field="math.CO", panel=True)               # a field's fixed author panel
    get_author_papers("terence tao")                       # every paper by an author key
    get_first_paper("terence tao")                         # id, month, URL
    get_paper("2608.00377")                                # one paper's tags and quotes

Every getter reads the local `data/` directory by default. Pass `source="github"` to
read the published files straight from the repository without cloning it, or a
directory path / base URL of your own.

Column-level documentation is in docs/schema.md; how the numbers were produced is in
docs/methodology.md.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"

#: Raw-file base for reading without a clone. Assumes the repository name below.
GITHUB_RAW = "https://raw.githubusercontent.com/epoch-research/ai-math-arxiv/main/data"

FILES = {
    "disclosures": "math_disclosures.csv",
    "examined": "math_examined.csv",
    "papers": "math_papers.csv.gz",
    "authors": "math_authors.csv.gz",
    "author_fields": "math_author_fields.csv.gz",
    "author_papers": "math_author_papers.csv.gz",
    "author_ids": "math_author_ids.csv.gz",
}

#: The value of `field` that means "every mathematics paper". The aggregate rows in
#: `examined` carry it; for the other tables it simply means "do not filter on field".
ALL_FIELDS = "all"

#: Columns that must stay strings: arXiv ids like "2606.00001" would otherwise parse
#: as floats and lose their trailing zero.
_STRING_COLUMNS = {
    "arxiv_id", "first_paper_id", "month", "first_paper_month", "last_paper_month",
    "field", "author", "name", "quote", "orcid", "openalex_author_id", "tag", "bucket",
    "attribution", "verifier", "tools_named", "vendors", "confidence", "tier", "url",
    "first_paper_url", "outcome",
}

#: Values of `papers.outcome`, in pipeline order.
OUTCOMES = (
    "not_examined",   # no parseable TeX source; not in any denominator
    "no_hit",         # examined; no AI-related keyword matched, so never read by the model
    "no_disclosure",  # read; no disclosure in the rendered text
    "subject_matter", # the paper is about AI; excluded from every disclosure series
    "denial",         # explicitly states no AI was used
    "disclosure",     # counted as disclosing; has rows in `disclosures`
    "unresolved",     # keyword hit, but no verdict (request errored or source not re-extracted)
)


# --- loading --------------------------------------------------------------------------


def _base(source: str | Path | None) -> str:
    if source is None:
        return str(DATA_DIR)
    if source == "github":
        return GITHUB_RAW
    return str(source)


@lru_cache(maxsize=None)
def _load(name: str, base: str) -> pd.DataFrame:
    path = f"{base}/{FILES[name]}"
    frame = pd.read_csv(path, dtype={c: "string" for c in _STRING_COLUMNS}, keep_default_na=False)
    # keep_default_na keeps an empty quote/orcid as "" rather than NaN; restore NaN-free
    # booleans and integers where the schema says so.
    for col in ("panel", "is_partial", "is_math_primary", "examined"):
        if col in frame.columns:
            frame[col] = frame[col].map({"True": True, "False": False, True: True, False: False})
    return frame


def load_table(name: str, source: str | Path | None = None) -> pd.DataFrame:
    """One table, unfiltered. `name` is a key of FILES."""
    if name not in FILES:
        raise KeyError(f"unknown table {name!r}; choose from {sorted(FILES)}")
    return _load(name, _base(source)).copy()


def get_all_tables(source: str | Path | None = None) -> dict[str, pd.DataFrame]:
    """Every table, unfiltered, keyed by name."""
    return {name: load_table(name, source) for name in FILES}


# --- filters --------------------------------------------------------------------------


def _month_mask(months: pd.Series, month: str | tuple[str, str] | None) -> pd.Series:
    """`month` may be a year ("2026"), a month ("2026-08"), or an inclusive
    (start, end) pair of either. None matches everything."""
    if month is None:
        return pd.Series(True, index=months.index)
    if isinstance(month, tuple):
        start, end = month
        end = f"{end}-12" if len(end) == 4 else end
        return (months >= start) & (months <= end)
    if len(month) == 4:
        return months.str.startswith(month)
    return months == month


def _field_mask(fields: pd.Series, field: str | None) -> pd.Series:
    if field is None or field == ALL_FIELDS:
        return pd.Series(True, index=fields.index)
    return fields == field


# --- papers -> disclosures ------------------------------------------------------------


_ID_PREFIX = re.compile(r"^(?:https?://arxiv\.org/(?:abs|pdf)/|arxiv:)", re.IGNORECASE)
_ID_VERSION = re.compile(r"v\d+$")


def normalize_arxiv_id(value: str) -> str:
    """`2608.00377v2`, `arXiv:2608.00377`, or an abs/pdf URL -> `2608.00377`.
    Old-style ids (`math/9709222`) pass through unchanged."""
    return _ID_VERSION.sub("", _ID_PREFIX.sub("", value.strip()))


def _id_mask(ids: pd.Series, arxiv_id: str | list[str] | None) -> pd.Series:
    if arxiv_id is None:
        return pd.Series(True, index=ids.index)
    wanted = [arxiv_id] if isinstance(arxiv_id, str) else list(arxiv_id)
    return ids.isin([normalize_arxiv_id(w) for w in wanted])


def get_disclosures(
    month: str | tuple[str, str] | None = None,
    field: str | None = ALL_FIELDS,
    bucket: str | None = None,
    tag: str | None = None,
    arxiv_id: str | list[str] | None = None,
    source: str | Path | None = None,
) -> pd.DataFrame:
    """Tag-level rows for papers counted as disclosing AI use.

    One row per (paper, tag): the arXiv id, its v1 month and primary field, the fine
    tag, the published bucket it rolls into, and the verbatim quote it rests on.
    A paper with three tags appears three times. `arxiv_id` takes one id or a list.
    """
    df = load_table("disclosures", source)
    mask = _month_mask(df["month"], month) & _field_mask(df["field"], field)
    mask &= _id_mask(df["arxiv_id"], arxiv_id)
    if bucket is not None:
        mask &= df["bucket"] == bucket
    if tag is not None:
        mask &= df["tag"] == tag
    return df[mask].reset_index(drop=True)


def get_disclosing_papers(
    month: str | tuple[str, str] | None = None,
    field: str | None = ALL_FIELDS,
    arxiv_id: str | list[str] | None = None,
    source: str | Path | None = None,
) -> pd.DataFrame:
    """One row per disclosing paper, with its tags, buckets, and quotes aggregated.

    `tags` and `buckets` are `;`-joined sorted sets; `quotes` joins each quote with
    ` | `. Use `get_disclosures` for one row per tag.
    """
    rows = get_disclosures(month=month, field=field, arxiv_id=arxiv_id, source=source)
    if rows.empty:
        return pd.DataFrame(
            columns=["arxiv_id", "url", "month", "field", "tags", "buckets", "quotes",
                     "tools_named", "vendors", "confidence"]
        )
    grouped = rows.groupby(["arxiv_id", "url", "month", "field"], sort=True)
    out = grouped.agg(
        tags=("tag", lambda s: "; ".join(sorted(set(s)))),
        buckets=("bucket", lambda s: "; ".join(sorted(set(s) - {""}))),
        quotes=("quote", lambda s: " | ".join(s)),
        tools_named=("tools_named", "first"),
        vendors=("vendors", "first"),
        confidence=("confidence", "first"),
    ).reset_index()
    return out.sort_values(["month", "field", "arxiv_id"]).reset_index(drop=True)


def get_papers(
    month: str | tuple[str, str] | None = None,
    field: str | None = ALL_FIELDS,
    outcome: str | None = None,
    arxiv_id: str | list[str] | None = None,
    source: str | Path | None = None,
) -> pd.DataFrame:
    """One row per listed paper with its outcome — "was this paper checked, and what
    came of it". `outcome` is one of OUTCOMES. Counting `disclosure` rows per cell
    reproduces `examined.papers_disclosing`; `examined == True` reproduces
    `papers_examined`."""
    df = load_table("papers", source)
    mask = _month_mask(df["month"], month) & _field_mask(df["field"], field)
    mask &= _id_mask(df["arxiv_id"], arxiv_id)
    if outcome is not None:
        if outcome not in OUTCOMES:
            raise ValueError(f"unknown outcome {outcome!r}; choose from {OUTCOMES}")
        mask &= df["outcome"] == outcome
    return df[mask].reset_index(drop=True)


def get_paper(arxiv_id: str, source: str | Path | None = None) -> dict[str, object] | None:
    """Everything published about one paper.

    Always includes the paper's `outcome` (see OUTCOMES). For a disclosing paper it
    also carries the tags with their quotes, the buckets, tools and vendors. Returns
    None only when the id is not a listed mathematics-primary paper in the covered
    range at all.
    """
    listed = get_papers(arxiv_id=arxiv_id, field=None, source=source)
    if listed.empty:
        return None
    row = listed.iloc[0]
    out: dict[str, object] = {
        "arxiv_id": str(row["arxiv_id"]),
        "url": f"https://arxiv.org/abs/{row['arxiv_id']}",
        "month": str(row["month"]),
        "field": str(row["field"]),
        "examined": bool(row["examined"]),
        "outcome": str(row["outcome"]),
    }
    rows = get_disclosures(arxiv_id=arxiv_id, field=None, source=source)
    if rows.empty:
        return out
    first = rows.iloc[0]
    return out | {
        "tier": str(first["tier"]),
        "buckets": sorted(set(rows["bucket"]) - {""}),
        "tags": [
            {"tag": r.tag, "bucket": r.bucket, "attribution": r.attribution,
             "verifier": r.verifier, "quote": r.quote}
            for r in rows.itertuples()
        ],
        "tools_named": [t for t in str(first["tools_named"]).split("; ") if t],
        "vendors": [v for v in str(first["vendors"]).split("; ") if v],
        "confidence": str(first["confidence"]),
    }


def get_examined(
    month: str | tuple[str, str] | None = None,
    field: str | None = None,
    source: str | Path | None = None,
) -> pd.DataFrame:
    """Denominators per (month, field): papers listed, examined, disclosing, denying.

    Rows with `field == "all"` are computed over every mathematics paper and are the
    ones to use for a math-wide rate; do not sum the field rows. `field=None` returns
    every row; `field="all"` returns only the aggregate rows.
    """
    df = load_table("examined", source)
    mask = _month_mask(df["month"], month)
    if field is not None:
        mask &= df["field"] == field
    return df[mask].reset_index(drop=True)


# --- authors --------------------------------------------------------------------------


def get_authors(
    field: str | None = None,
    panel: bool | None = None,
    source: str | Path | None = None,
) -> pd.DataFrame:
    """Author rows, optionally restricted to authors active in a field and/or in its panel.

    `field` means "has at least one math-primary paper with that primary category".
    `panel=True` keeps only members of that field's fixed author panel (docs/methodology.md);
    `panel=False` keeps the field's non-members. With `field=None`, `panel=True` means
    "in at least one field's panel".
    """
    authors = load_table("authors", source)
    if field in (None, ALL_FIELDS) and panel is None:
        return authors
    fields = load_table("author_fields", source)
    if field not in (None, ALL_FIELDS):
        fields = fields[fields["field"] == field]
    if panel is not None:
        fields = fields[fields["panel"] == bool(panel)]
    keep = set(fields["author"])
    return authors[authors["author"].isin(keep)].reset_index(drop=True)


def get_author_fields(
    author: str | None = None,
    field: str | None = None,
    panel: bool | None = None,
    source: str | Path | None = None,
) -> pd.DataFrame:
    """(author, field) rows: in-field paper counts and the per-field panel flag."""
    df = load_table("author_fields", source)
    mask = pd.Series(True, index=df.index)
    if author is not None:
        mask &= df["author"] == author
    if field not in (None, ALL_FIELDS):
        mask &= df["field"] == field
    if panel is not None:
        mask &= df["panel"] == bool(panel)
    return df[mask].reset_index(drop=True)


def get_author_papers(
    author: str | None = None,
    field: str | None = None,
    source: str | Path | None = None,
) -> pd.DataFrame:
    """Every (author, paper) link, or those of one author key / one primary field."""
    df = load_table("author_papers", source)
    mask = pd.Series(True, index=df.index)
    if author is not None:
        mask &= df["author"] == author
    if field not in (None, ALL_FIELDS):
        mask &= df["field"] == field
    return df[mask].reset_index(drop=True)


def get_first_paper(author: str, source: str | Path | None = None) -> dict[str, str] | None:
    """The author's first paper in arXiv's mathematics set: id, month, URL. None if the
    key is unknown."""
    df = load_table("authors", source)
    row = df[df["author"] == author]
    if row.empty:
        return None
    r = row.iloc[0]
    return {
        "arxiv_id": str(r["first_paper_id"]),
        "month": str(r["first_paper_month"]),
        "url": str(r["first_paper_url"]),
    }


def get_author_ids(
    author: str | None = None,
    with_orcid: bool | None = None,
    source: str | Path | None = None,
) -> pd.DataFrame:
    """The OpenAlex / ORCID crosswalk. One row per (author key, OpenAlex id, ORCID)
    with the number of shared papers supporting the link; best-supported row first
    within each author. `with_orcid=True` keeps rows carrying an ORCID."""
    df = load_table("author_ids", source)
    mask = pd.Series(True, index=df.index)
    if author is not None:
        mask &= df["author"] == author
    if with_orcid is not None:
        mask &= (df["orcid"] != "") == bool(with_orcid)
    return df[mask].reset_index(drop=True)


def normalize_author(name: str) -> str:
    """The author key for a display name, so callers can look people up by name.

    This is the same rule the pipeline uses, reduced to what a name string needs:
    lower-case, punctuation to spaces, accents folded, whitespace collapsed. TeX
    escapes are not handled here — the published keys were computed from raw arXiv
    bylines with TeX resolved first.
    """
    import unicodedata

    folded = "".join(
        c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c)
    )
    folded = folded.translate(str.maketrans("øØłŁđĐßæÆœŒ", "oOlLdDsaAoO"))
    cleaned = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", folded)).strip().lower()
    return cleaned
