# Math Research Impacts Data

The tracker's charts are at <https://epoch.ai/data/arxiv>.

## Usage

Clone the repository and import the module; the data files are committed under
`data/` and need nothing but pandas.

```python
from arxiv_math_ai_data import get_disclosures, get_disclosing_papers, get_examined, get_paper

get_disclosures(month="2026-08", field="math.CO")   # one row per (paper, tag), with quotes
get_disclosing_papers(month="2026")                  # one row per paper, tags aggregated
get_examined(field="all")                            # denominators, math-wide, per month
get_paper("2608.00377")                              # one paper: outcome, tags, quotes, tools
get_papers(month="2026-08", outcome="no_hit")        # every listed paper, with its outcome
```

Look a paper up by arXiv id in any spelling: `2608.00377`, `2608.00377v2`,
`arXiv:2608.00377`, or its abs/pdf URL. Every listed paper has an `outcome`, so
"was this paper checked at all" always has an answer: `not_examined`, `no_hit`,
`no_disclosure`, `subject_matter`, `denial`, `disclosure`, or `unresolved`.

```python
from arxiv_math_ai_data import get_monthly

get_monthly("ai_ack_rate", field="math.CO")               # one chart series, with a value column
get_monthly("ai_ack_purpose", period="2026", category="generated")
get_monthly("author_tenure", period="2026-08")             # colour-by-career-length, one month
```

```python
from arxiv_math_ai_data import get_authors, get_author_papers, get_first_paper, get_author_ids

get_authors(field="math.CO", panel=True)   # the combinatorics panel
get_author_papers("terence tao")           # every paper by that author key
get_first_paper("terence tao")             # {'arxiv_id': ..., 'month': ..., 'url': ...}
get_author_ids("terence tao")              # OpenAlex ids and ORCID, best-supported first
```

Or fetch everything at once, or read straight from GitHub without cloning:

```python
from arxiv_math_ai_data import get_all_tables

tables = get_all_tables()                  # dict of eight DataFrames
tables = get_all_tables(source="github")   # same, read from the raw files online
```

Month arguments accept a year (`"2026"`), a month (`"2026-08"`), or an inclusive
`(start, end)` pair. Field arguments take an arXiv primary category (`"math.CO"`) or
`"all"`. Author keys are normalised names; `normalize_author("Terence Tao")` gives
you the key for a display name.

## Tables

See [`docs/schema.md`](docs/schema.md) for the column-level schema of the row-level
files, [`docs/monthly-series.md`](docs/monthly-series.md) for the chart file and its
metric registry, and [`docs/methodology.md`](docs/methodology.md) for how the values
were produced.

| Table | File | Grain | Rows | Key columns |
|-------|------|-------|------|-------------|
| `monthly` | `data/arxiv_trends_monthly.csv` | Metric × field × month × population × category | ~50,000 | `numerator`, `denominator`, `is_partial`, `provenance` |
| `disclosures` | `data/math_disclosures.csv` | Paper × use tag | ~8,000 | `arxiv_id`, `month`, `field`, `tag`, `bucket`, `quote` |
| `examined` | `data/math_examined.csv` | Month × field (+ `all`) | ~3,200 | `papers_listed`, `papers_examined`, `papers_disclosing`, `papers_denying` |
| `papers` | `data/math_papers.csv.gz` | Listed paper | ~160,000 | `examined`, `outcome` |
| `authors` | `data/math_authors.csv.gz` | Author key | ~342,000 | `name`, `first_paper_id`, `first_paper_month`, `n_papers` |
| `author_fields` | `data/math_author_fields.csv.gz` | Author × math field | ~354,000 | `n_papers_in_field`, `n_papers_2019_2022`, `panel` |
| `author_papers` | `data/math_author_papers.csv.gz` | Author × paper | ~1,740,000 | `arxiv_id`, `month`, `field`, `is_math_primary` |
| `author_ids` | `data/math_author_ids.csv.gz` | Author × OpenAlex id × ORCID | ~207,000 | `openalex_author_id`, `orcid`, `n_shared_papers` |

`data/manifest.json` records the snapshot: when it was generated, from which
pipeline commit, and the row counts and coverage figures for that release.

## Refresh

The pipeline runs monthly. 

## Citation

> Epoch AI (2026). *AI use in mathematics research: arXiv disclosures and author
> tables.* https://github.com/epoch-research/ai-math-arxiv

Licensed under [CC BY 4.0](LICENSE). 
