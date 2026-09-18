# AI Use in Math Research data explorer

This repository contains the data for Epoch's AI Use in Math Research [data explorer](https://epoch.ai/data/arxiv). 

Read the full methodology here. We use the following data: 
 - arXiv metadata sourced from the [arXiv OAI-PMH interface](https://info.arxiv.org/help/oa/index.html)
 - arXiv full-text data sourced from the [arXiv Amazon S3 bulk data](https://info.arxiv.org/help/bulk_data_s3.html)

## Accessing the data

Access the data by the following Python functions. 

| Call | Output | Filters |
|------|--------------|---------|
| `get_monthly` | the chart series | metric, field, period, population, category |
| `get_disclosures` | one row per paper, tag and quote | month, field, bucket, tag, arxiv_id |
| `get_disclosing_papers` | one row per disclosing paper, with all tags aggregated | month, field, arxiv_id |
| `get_papers` | one row per paper, with its outcome | month, field, outcome, arxiv_id |
| `get_tools` | one row per tool, with the crediting sentence | arxiv_id, vendor, tool, month, field |
| `get_paper` | one paper: outcome, tags, quotes, tools | arxiv_id |
| `get_examined` | the count of all papers, per month and field | month, field |
| `load_table` | one table, unfiltered | name |
| `get_all_tables` | all five tables, keyed by name | — |


Everything returns a pandas DataFrame except `get_paper`, which returns a dict (or
`None` for an unlisted id), and `get_all_tables`, which returns a dict of DataFrames.
The five table names are `monthly`, `disclosures`, `tools`, `examined`, `papers`. 

Each paper has an `outcome`, one of the following: 

| `outcome` | Meaning |
|-----------|---------|
| `not_examined` | no parseable TeX source; not in any denominator |
| `no_hit` | examined; no AI-related keyword matched, so never read by the model |
| `no_disclosure` | read; no disclosure in the rendered text (a name collision, a citation, or a disclosure present only in TeX comments) |
| `subject_matter` | the paper is about AI, and no use was counted |
| `denial` | the authors state no AI was used, and disclose no use |
| `disclosure` | counted as disclosing; its tags and quotes are in `disclosures` |
| `unresolved` | keyword hit, but no verdict: the request errored or the source could not be re-extracted; in the denominator, not the numerator |

If a paper does contain an AI-use acknowledgment, the `tag` will return what types of AI-use acknowledgments the paper contains, and the `quote` associated with the tag is a verbatim quote from the paper justifying the inclusion of that tag. 

See example code:  

```python
from arxiv_math_ai_data import get_disclosures, get_monthly, get_paper

get_disclosures(month="2026-08", field="math.CO")   # a list of papers and AI acknowledgments
get_monthly("ai_ack_rate", field="math.CO")         # a chart series
get_paper("2608.00377")                             # metadata and acknowledgment info for one paper
```

## Arguments

- **Months** take a year (`"2026"`), a month (`"2026-08"`), or an inclusive
  `(start, end)` pair.
- **Fields** take an arXiv primary category (`"math.CO"`) or `"all"`.
- **arXiv ids** are accepted in any spelling: `2608.00377v2`, `arXiv:2608.00377`, an abs
  or pdf URL. `normalize_arxiv_id` is the rule.
- **`source`** is on every call. Pass `source="github"` to read the published files
  online instead of cloning, or a directory path of your own.

## Replicating our classification 

The prompt used to classify the AI use acknowledgments is in `docs/classifier-prompt.md`. 

## Citation

> Epoch AI (2026). *AI use in Math Research data.* https://github.com/epoch-research/ai-math-arxiv

Licensed under [CC BY 4.0](LICENSE). Quotes are taken from arXiv paper text and are not covered under this license. 
