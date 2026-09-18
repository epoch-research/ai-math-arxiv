"""AI use in mathematics research, measured on arXiv — the public dataset.

One dataset plus the chart series, five tables, read from the CSV files in `data/`:

  THE MONTHLY SERIES
    monthly        the aggregate file the tracker's charts draw, one row per
                   (metric, field, month, population, category), numerator/denominator

  PAPERS -> AI-USE DISCLOSURES
    disclosures    one row per (paper, use tag) with the verbatim quote behind the tag
    examined       per (month, field): papers listed, examined, disclosing, denying
    papers         one row per listed paper with its outcome (was it checked, and what
                   came of it): not_examined / no_hit / no_disclosure / subject_matter /
                   denial / disclosure / unresolved
    tools          one row per (disclosing paper, credited tool): the tool verbatim, the
                   vendor it maps to, and the sentence in the paper crediting it

Usage:

    from arxiv_math_ai_data import get_disclosures, get_monthly

    get_disclosures(month="2026-08", field="math.CO")     # tag rows, with quotes
    get_disclosing_papers(month="2026")                    # one row per paper
    get_paper("2608.00377")                                # one paper's tags and quotes
    get_papers(month="2026-08", outcome="denial")          # papers that deny AI use
    get_tools(vendor="anthropic", month="2026")            # tool receipts behind a vendor
    get_examined(month="2026")                             # the denominators
    get_monthly("ai_ack_rate", field="math.CO")            # a chart series, ready to plot

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
    "monthly": "arxiv_trends_monthly.csv",
    "disclosures": "math_disclosures.csv",
    "examined": "math_examined.csv",
    "papers": "math_papers.csv.gz",
    "tools": "math_tools.csv",
}

#: The value of `field` that means "every mathematics paper". The aggregate rows in
#: `examined` carry it; for the other tables it simply means "do not filter on field".
ALL_FIELDS = "all"

#: Columns that must stay strings: arXiv ids like "2606.00001" would otherwise parse
#: as floats and lose their trailing zero.
_STRING_COLUMNS = {
    "arxiv_id", "month", "field", "quote", "tag", "bucket", "second_reader",
    "tools_named", "vendors", "confidence", "url", "tool", "vendor", "outcome",
    "metric", "period", "population", "category", "provenance",
}

#: The aggregate file names the math-wide aggregate `math`; the row-level tables and
#: this module's filter arguments say `all`. `get_monthly` translates.
MONTHLY_ALL_FIELD = "math"

#: Values of `papers.outcome`, in pipeline order.
OUTCOMES = (
    "not_examined",   # no parseable TeX source; not in any denominator
    "no_hit",         # examined; no AI-related keyword matched, so never read by the model
    "no_disclosure",  # read; no use of AI counted in the rendered text
    "subject_matter", # the paper is about AI, and no use of AI in producing it was counted
    "denial",         # explicitly states no AI was used
    "disclosure",     # counted as acknowledging AI use; has rows in `disclosures`
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
    for col in ("is_partial", "examined"):
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


# --- the monthly series ---------------------------------------------------------------


def get_monthly(
    metric: str | None = None,
    field: str | None = ALL_FIELDS,
    period: str | tuple[str, str] | None = None,
    population: str | None = "all",
    category: str | None = None,
    source: str | Path | None = None,
) -> pd.DataFrame:
    """Rows of the chart series file: one per (metric, field, period, population, category).

    Every metric is stored as `numerator` / `denominator`; the value is their ratio, and
    rolling months up to quarters or years is summing both columns and dividing. `field`
    defaults to the math-wide aggregate (`"all"`, stored as `"math"`); pass a category
    such as `"math.CO"`, or None for every field. `population` is `"all"` or `"panel"`
    (papers with an author in the field's fixed panel); None returns both. See
    docs/monthly-series.md for the metric registry and reading rules.
    """
    df = load_table("monthly", source)
    mask = _month_mask(df["period"], period)
    if metric is not None:
        mask &= df["metric"] == metric
    if field is not None:
        mask &= df["field"] == (MONTHLY_ALL_FIELD if field == ALL_FIELDS else field)
    if population is not None:
        mask &= df["population"] == population
    if category is not None:
        mask &= df["category"] == category
    out = df[mask].reset_index(drop=True)
    out["value"] = out["numerator"] / out["denominator"]
    return out


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

    `tags`, `buckets` and `confidence` are `;`-joined sorted sets (confidence is per
    tag, so a paper with one plain and one hedged tag reads `high; medium`); `quotes`
    joins each quote with ` | `. Use `get_disclosures` for one row per tag.
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
        confidence=("confidence", lambda s: "; ".join(sorted(set(s) - {""}))),
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


def get_tools(
    arxiv_id: str | list[str] | None = None,
    vendor: str | None = None,
    tool: str | None = None,
    month: str | tuple[str, str] | None = None,
    field: str | None = ALL_FIELDS,
    source: str | Path | None = None,
) -> pd.DataFrame:
    """The receipts behind the vendor series: one row per (disclosing paper, credited
    tool), with the tool spelled as the paper spells it, the vendor category it maps to,
    and the verbatim sentence crediting it.

    `vendor` is a contract vendor id (`openai`, `anthropic`, ...), `unnamed` for a
    generic phrase such as "an LLM", or `""` for a credited tool that is not an AI
    vendor (Lean, Grammarly). `tool` matches the verbatim spelling exactly. A paper's
    `vendors` in `disclosures` is the set of non-empty, non-`unnamed` vendors of its
    rows here, or `unnamed` if there are none.
    """
    df = load_table("tools", source)
    mask = _month_mask(df["month"], month) & _field_mask(df["field"], field)
    mask &= _id_mask(df["arxiv_id"], arxiv_id)
    if vendor is not None:
        mask &= df["vendor"] == vendor
    if tool is not None:
        mask &= df["tool"] == tool
    return df[mask].reset_index(drop=True)


def get_paper(arxiv_id: str, source: str | Path | None = None) -> dict[str, object] | None:
    """Everything published about one paper.

    Always includes the paper's `outcome` (see OUTCOMES). For a disclosing paper it
    also carries the tags with their quotes, how the second reader backed each one,
    the tagger's per-tag confidence, the buckets, the vendors, and under `tools` each
    credited tool with the sentence crediting it. Returns None only when the id is not
    a listed mathematics-primary paper in the covered range at all.
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
        "buckets": sorted(set(rows["bucket"]) - {""}),
        "tags": [
            {"tag": r.tag, "bucket": r.bucket, "second_reader": r.second_reader,
             "confidence": r.confidence, "quote": r.quote}
            for r in rows.itertuples()
        ],
        "tools": [
            {"tool": r.tool, "vendor": r.vendor, "quote": r.quote}
            for r in get_tools(arxiv_id=arxiv_id, field=None, source=source).itertuples()
        ],
        "vendors": [v for v in str(first["vendors"]).split("; ") if v],
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
