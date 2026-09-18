# Data Schema

Column-level reference for the four row-level tables in `data/`. The fifth, the
monthly chart series, is in [`monthly-series.md`](monthly-series.md).

## Conventions

- **Months** are `YYYY-MM` and always mean the paper's **first-version (v1)
  submission month**.
- **Fields** are arXiv primary categories (`math.CO`), named at
  <https://arxiv.org/archive/math>. A cross-listed paper counts once, under its
  primary. The value `all` in `examined`
  is the aggregate over every mathematics-primary paper, computed over the papers
  themselves and never summed from field rows.
- **arXiv ids** are strings (`2606.00001`, `math/0601001`); load them as strings or
  the trailing zeros are lost. `url` columns point to `https://arxiv.org/abs/<id>`.
- **Empty strings** mean "none": an empty `vendor` is a credited tool that is not a
  vendor's product, an empty `bucket` is a tag that counts toward no published bucket.
- **Booleans** are written `True` / `False`. Multi-valued text columns join with `; `.

## `disclosures` — `data/math_disclosures.csv`

One row per (paper, use tag). Every paper here is counted in the published disclosure
rate, and every paper counted in the rate is here.

| Column | Type | Notes |
|--------|------|-------|
| `arxiv_id` | str | |
| `url` | str | `https://arxiv.org/abs/<arxiv_id>` |
| `month` | str | v1 submission month |
| `field` | str | primary category |
| `tag` | str | fine use tag |
| `bucket` | str | the published use-case bucket the tag rolls into, or empty when the tag's series is not published; the bucket set is the `ai_ack_purpose` categories in [`monthly-series.md`](monthly-series.md) |
| `second_reader` | str | how the second reader backed this tag: `reread_confirmed` (blind re-read of the paper) or `pair_supported` (ruled on the tag and its quote) |
| `quote` | str | verbatim text from the paper supporting the tag, whitespace collapsed |
| `tools_named` | str | every AI tool or proof assistant the paper credits, verbatim, `; `-joined; paper-level, repeated on each of the paper's rows |
| `vendors` | str | vendors derived from `tools_named`; `; `-joined; paper-level |
| `confidence` | str | the tagger's confidence in this tag: `high`, `medium`, `low` |

Buckets are multi-label: a paper's buckets are the set of non-empty `bucket` values
on its rows, and they partition nothing.

## `tools` — `data/math_tools.csv`

One row per (paper, credited tool): the receipt behind `vendors`. Only tools whose
crediting sentence was found in the paper are listed.

| Column | Type | Notes |
|--------|------|-------|
| `arxiv_id` | str | |
| `url` | str | |
| `month` | str | v1 submission month |
| `field` | str | primary category |
| `tool` | str | the tool as the paper names it, verbatim |
| `vendor` | str | the vendor it maps to; empty when the tool is not a vendor's product or is unmapped |
| `quote` | str | the sentence crediting it |

A paper's `vendors` recomputes from its rows here as the non-empty, non-`unnamed`
vendors, else `unnamed`. A paper that named no vendor at all is `unnamed` in
`disclosures` and has no row here: there is nothing to receipt.

## `examined` — `data/math_examined.csv`

One row per (month, field), plus one `all` row per month. The published disclosure
rate for a cell is `papers_disclosing / papers_examined`.

| Column | Type | Notes |
|--------|------|-------|
| `month` | str | v1 submission month |
| `field` | str | primary category, or `all` |
| `papers_listed` | int | mathematics-primary papers submitted in the cell |
| `papers_examined` | int | of those, papers whose TeX source was retrieved and parsed — the denominator |
| `papers_disclosing` | int | examined papers counted as disclosing AI use |
| `papers_denying` | int | examined papers that explicitly state no AI was used, and disclose no use |
| `is_partial` | bool | the month was still open, or within announcement lag, at the snapshot |

Rows exist for every cell with at least one examined paper; a missing cell means no
data, never a measured zero.

## `papers` — `data/math_papers.csv.gz`

One row per mathematics-primary paper listed from January 2023 to the last examined
month: the table for "was this paper checked at all, and what came of it".

| Column | Type | Notes |
|--------|------|-------|
| `arxiv_id` | str | |
| `month` | str | v1 submission month |
| `field` | str | primary category |
| `examined` | bool | source was retrieved and parsed; the paper is in the denominator |
| `outcome` | str | one of the values below |

| `outcome` | Meaning |
|-----------|---------|
| `not_examined` | no parseable TeX source; not in any denominator |
| `no_hit` | examined; no AI-related keyword matched, so never read by the model |
| `no_disclosure` | read; no disclosure in the rendered text (a name collision, a citation, or a disclosure present only in TeX comments) |
| `subject_matter` | the paper is about AI, and no use was counted |
| `denial` | the authors state no AI was used, and disclose no use |
| `disclosure` | counted as disclosing; its tags and quotes are in `disclosures` |
| `unresolved` | keyword hit, but no verdict: the request errored or the source could not be re-extracted; in the denominator, not the numerator |

Per (month, field), `examined == True` counts to `examined.papers_examined`,
`disclosure` to `papers_disclosing`, `denial` to `papers_denying`, and every row to
`papers_listed`.

## Coverage

The disclosure, tools, examined and papers tables run from 2023-01 to the latest
month in `data/manifest.json`.
