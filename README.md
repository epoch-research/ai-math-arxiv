# AI Use in Math Research data explorer

This repository contains the data for Epoch's AI Use in Math Research [data explorer](https://epoch.ai/data/arxiv). 

Read the full methodology here. We use the following data: 
 - arXiv metadata sourced from the [arXiv OAI-PMH interface](https://info.arxiv.org/help/oa/index.html)
 - arXiv full-text data sourced from the [arXiv Amazon S3 bulk data](https://info.arxiv.org/help/bulk_data_s3.html)
 - OpenAlex authorship information for each paper sourced from the [OpenAlex API](https://help.openalex.org/api/)

## Accessing the data

Access the data using this repository by calling the following Python functions. 
See an example below. 

```python
from arxiv_math_ai_data import get_disclosures, get_monthly, get_paper

get_disclosures(month="2026-08", field="math.CO")   # tag rows, with quotes
get_monthly("ai_ack_rate", field="math.CO")         # a chart series, ready to plot
get_paper("2608.00377")                             # one paper, end to end
```

| Call | Output | Filters |
|------|--------------|---------|
| `get_monthly` | the chart series | metric, field, period, population, category |
| `get_disclosures` | one row per paper, tag and quote | month, field, bucket, tag, arxiv_id |
| `get_disclosing_papers` | one row per disclosing paper, tags aggregated | month, field, arxiv_id |
| `get_papers` | one row per listed paper, with its outcome | month, field, outcome, arxiv_id |
| `get_tools` | one row per credited tool, with the crediting sentence | arxiv_id, vendor, tool, month, field |
| `get_paper` | one paper: outcome, tags, quotes, tools | arxiv_id |
| `get_examined` | the denominators, per month and field | month, field |
| `load_table` | one table, unfiltered | name |
| `get_all_tables` | all five, keyed by name | — |

Everything returns a pandas DataFrame except `get_paper`, which returns a dict (or
`None` for an unlisted id), and `get_all_tables`, which returns a dict of DataFrames.
The five table names are `monthly`, `disclosures`, `tools`, `examined`, `papers`. 

## Arguments

- **Months** take a year (`"2026"`), a month (`"2026-08"`), or an inclusive
  `(start, end)` pair.
- **Fields** take an arXiv primary category (`"math.CO"`) or `"all"`.
- **arXiv ids** are accepted in any spelling: `2608.00377v2`, `arXiv:2608.00377`, an abs
  or pdf URL. `normalize_arxiv_id` is the rule.
- **`source`** is on every call. Pass `source="github"` to read the published files
  online instead of cloning, or a directory path of your own.

## Citation

> Epoch AI (2026). *AI use in Math Research data.* https://github.com/epoch-research/ai-math-arxiv

Licensed under [CC BY 4.0](LICENSE).
