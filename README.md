# AI use in mathematics research, on arXiv

Every mathematics paper counted as disclosing AI use since January 2023, with the
verbatim quote behind each tag and the tools it credits; the author tables behind the
panel and tenure series; and the monthly series Epoch AI's charts draw.
Charts: <https://epoch.ai/data/arxiv>.

Nine tables sit in [`data/`](data/), committed. Columns are documented in
[`docs/schema.md`](docs/schema.md) and [`docs/monthly-series.md`](docs/monthly-series.md),
how the numbers were produced in [`docs/methodology.md`](docs/methodology.md), and the
snapshot itself in [`data/manifest.json`](data/manifest.json).

## Reading it

Needs pandas and nothing else.

```python
from arxiv_math_ai_data import get_disclosures, get_monthly, get_paper

get_disclosures(month="2026-08", field="math.CO")   # tag rows, with quotes
get_monthly("ai_ack_rate", field="math.CO")         # a chart series, ready to plot
get_paper("2608.00377")                             # one paper, end to end
```

| Call | What you get | Filters |
|------|--------------|---------|
| `get_monthly` | the chart series, plus a `value` column | metric, field, period, population, category |
| `get_disclosures` | one row per paper, tag and quote | month, field, bucket, tag, arxiv_id |
| `get_disclosing_papers` | one row per disclosing paper, tags aggregated | month, field, arxiv_id |
| `get_papers` | one row per listed paper, with its outcome | month, field, outcome, arxiv_id |
| `get_tools` | one row per credited tool, with the crediting sentence | arxiv_id, vendor, tool, month, field |
| `get_paper` | one paper: outcome, tags, quotes, tools | arxiv_id |
| `get_examined` | the denominators, per month and field | month, field |
| `get_authors` | one row per author key | field, panel |
| `get_author_fields` | one row per author and field, with the panel flag | author, field, panel |
| `get_author_papers` | one row per author and paper | author, field |
| `get_first_paper` | that author's first paper in arXiv mathematics | author |
| `get_author_ids` | the OpenAlex and ORCID crosswalk | author, with_orcid |
| `load_table` | one table, unfiltered | name |
| `get_all_tables` | all nine, keyed by name | — |

Everything returns a DataFrame except `get_paper` and `get_first_paper`, which return
a dict.

## Arguments

- **Months** take a year (`"2026"`), a month (`"2026-08"`), or an inclusive
  `(start, end)` pair.
- **Fields** take an arXiv primary category (`"math.CO"`) or `"all"`.
- **arXiv ids** are accepted in any spelling: `2608.00377v2`, `arXiv:2608.00377`, an abs
  or pdf URL. `normalize_arxiv_id` is the rule.
- **Author keys** are normalised names; `normalize_author("Terence Tao")` gives the key.
- **`source`** is on every call. Pass `source="github"` to read the published files
  online instead of cloning, or a directory path of your own.

## Citation

> Epoch AI (2026). *AI use in mathematics research: arXiv disclosures and author
> tables.* https://github.com/epoch-research/ai-math-arxiv

Licensed under [CC BY 4.0](LICENSE). Paper metadata and author bylines are from arXiv;
author identifiers are from OpenAlex.
