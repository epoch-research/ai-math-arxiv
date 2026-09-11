# AI Use in Mathematics Research — arXiv Data

Per-paper and per-author data behind Epoch AI's tracker of how AI is changing
mathematical research practice, measured on arXiv, together with the monthly series
the tracker's charts draw. Two datasets and the chart file:

- **Papers → AI-use disclosures.** Every mathematics paper counted as disclosing AI
  use, from January 2023 to the latest complete month, with the use-case tags assigned to it
  and the verbatim quote from the paper that justifies each tag. Alongside it, the
  denominators: how many papers were listed and examined in each month and field.
- **Authors.** Every author key in arXiv's mathematics set with their first paper,
  their paper list, per-field paper counts, membership of each field's fixed author
  panel, and a crosswalk to OpenAlex author ids and ORCIDs.

- **The monthly series.** The aggregate file the charts read, one row per metric,
  field, month, population and category, stored as numerator and denominator. Every
  series in it can be rebuilt from the two datasets above, and the tests do so for
  the disclosure rate, the paper counts, and the career-length composition.

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

## Reading the data honestly

A few properties of these tables are easy to get wrong.

- **The disclosure rate is `papers_disclosing / papers_examined`**, from the
  `examined` table, and the `disclosures` table lists exactly those papers. The
  `ai_ack_rate` rows of the monthly file carry the same two numbers. The
  denominator is papers whose TeX source we could read, not papers listed; the two
  differ by a few percent. Use the `field == "all"` rows for a math-wide figure; the
  field rows do not sum to it, because small fields are included here and the
  aggregate is computed over papers.
- **Every rate is a floor.** Papers reach the classifier only if a keyword scan finds
  an AI-related term in them. A paper that discloses AI use in words the scan does
  not catch is not here, and the size of that gap is unknown.
- **Recent months rise after publication.** Disclosure statements are often added
  when a paper is revised for a journal. Each monthly refresh re-reads revised papers,
  so a month's count is "as of the snapshot" and legitimately grows for a while.
- **Tags are model judgements with receipts.** A language model assigned the tags;
  a second model tried to refute every one, and every surviving tag carries the
  verbatim quote it rests on. The `verifier` column says whether the second reader
  found the tag `supported` or `borderline`. Borderline tags are included pending
  human review. If you believe a paper is mis-tagged, open an issue citing the arXiv
  id: the quote is there to be argued with.
- **Author keys are normalised names, not people.** Two people with the same name
  share a key, and one person written two ways has two keys. The `author_ids`
  crosswalk to OpenAlex and ORCID is the way to a stronger identity, and it is
  published as a long table precisely because the two sources disagree in both
  directions.
- **The panel is a definition, not a ranking.** A field's panel is the set of authors
  with at least three papers in that field during 2019–2022, at least five
  core-journal papers in OpenAlex, and at least one further mathematics paper from
  2023 on. It exists so that a change in output can be read as a change in what the
  same people did, and nothing more.

## Coverage

The paper-level tables and the monthly series begin in **January 2023**. The pipeline
measures from 2018, but 2018–2022 holds four disclosing papers in five years and was
read as excerpts rather than full text, so the public dataset starts where the
full-text tier does. The author tables keep the full history of arXiv mathematics
from 1989, because first papers and career lengths depend on it.

## What is deliberately absent

Disclosures the authors wrote only in TeX comments, and then did not render in the
PDF, are counted in an aggregate sub-series on the tracker but are not listed per
paper here. Papers the model judged to be *about* AI are excluded from the disclosure
tables, even when their authors also used AI. There is no per-author "uses AI"
column: the tables let anyone compute it, but it is not a judgement this dataset
makes.

## Refresh

The pipeline runs monthly, after arXiv publishes the previous month's source
archives. A refresh replaces the files in `data/` and updates `manifest.json`; the
diff is the changelog. History can change on a refresh, for the reasons above. The
monthly series file is the one the website's charts read (see "Publishing to S3"
below), so the charts and this repository describe one snapshot. Two tracker metrics are not in
it, because nothing here can reproduce them: Lean formalization claims and pages per
paper.

## Publishing to S3

Every push to `main` that touches `data/` runs
[`.github/workflows/upload-s3.yml`](.github/workflows/upload-s3.yml), which copies the
files in `data/` to the datahub S3 bucket under the `ai-math-arxiv/` prefix, plus a
gzipped copy of the monthly series, `ai-math-arxiv/arxiv_trends_monthly.csv.gz`. That
gzipped file is what the website's data pipeline
([epoch-website-astro](https://github.com/epoch-research/epoch-website-astro),
`scripts/datahub/update_arxiv_databases.py`) fetches on its hourly run and serves at
<https://epoch.ai/data/arxiv_trends_monthly.csv.gz>. The workflow can also be run by hand
from the Actions tab.

Authentication is GitHub's OIDC, no AWS keys: the job assumes the IAM role
`epoch-gh-actions-datahub-ai-math-arxiv`, which must trust this repository's `main`
branch and allow `s3:PutObject` on `arn:aws:s3:::<bucket>/ai-math-arxiv/*`. The account,
region and bucket come from the organization variables `DATAHUB_UPDATE_AWS_ACCOUNT_ID`,
`DATAHUB_UPDATE_AWS_REGION` and `DATAHUB_UPDATE_S3_BUCKET`, which have to be shared with
this repository (epoch-research → Settings → Secrets and variables → Actions →
Variables → Selected repositories).

## Citation

> Epoch AI (2026). *AI use in mathematics research: arXiv disclosures and author
> tables.* https://github.com/epoch-research/ai-math-arxiv

Licensed under [CC BY 4.0](LICENSE). Paper metadata and author bylines are from
arXiv; author identifiers are from OpenAlex.
