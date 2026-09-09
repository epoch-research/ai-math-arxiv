# The monthly series: `data/arxiv_trends_monthly.csv`

The aggregate file the tracker's charts draw, at monthly grain. It is the same file
the website reads, minus two metrics the row-level tables in this repository cannot
reproduce (`lean_proof_rate`, `pages_per_paper`). Everything else in it can be
rebuilt from `disclosures`, `examined`, `papers`, `authors` and `author_papers`, and
the test suite checks the disclosure rate, the paper counts and the tenure
composition against them.

## Columns

| Column        | Type   | Notes                                                                 |
| ------------- | ------ | --------------------------------------------------------------------- |
| `metric`      | string | snake_case metric id, see the registry below                          |
| `field`       | string | primary arXiv category (`math.CO`), or `math` for every mathematics paper |
| `period`      | string | `YYYY-MM`, the v1 submission month                                     |
| `population`  | string | `all`, or `panel` (papers with an author in the field's fixed panel)    |
| `category`    | string | sub-breakdown within a metric; empty when the metric has none          |
| `numerator`   | number | see below                                                              |
| `denominator` | number | never zero; the row is omitted instead                                 |
| `is_partial`  | bool   | the period was still open when this row was computed                   |
| `provenance`  | string | which pipeline stage and input version produced the row                |

A row is identified by (`metric`, `field`, `period`, `population`, `category`).
There is no `value` column in the file; `get_monthly` adds one as
`numerator / denominator`.

Note the naming difference from the row-level tables: the math-wide aggregate is
`math` here and `all` there. `get_monthly(field="all")` translates.

## Everything is a ratio

Every metric is stored as a numerator and a denominator, including plain counts:

| Metric kind | `numerator`              | `denominator`        | Reading      |
| ----------- | ------------------------ | -------------------- | ------------ |
| Count       | papers                   | `1`                  | a count      |
| Rate        | papers with the property | papers we could read | a proportion |
| Mean        | sum over papers          | papers contributing  | an average   |

**To roll monthly up to a quarter or a year, sum both columns and divide.** That is
correct for all three kinds, which it would not be if rates or means were stored
directly: averaging an average weights a quiet month equally with a busy one.

## Denominators are not interchangeable

Full-text metrics are measured over **papers whose source we could read**, never
papers listed. Metadata metrics have their own denominators: `authors_band` and
`authors_per_paper` count only papers whose author list could be parsed, so their
denominator is smaller than `papers_total`. `author_tenure` is denominated in
**authors**, not papers, and must never share an axis with a paper metric.

Rows whose denominator would be zero are omitted, so a gap means "no data", never
"measured zero".

## Fields

`field` is the paper's **primary** category only. Per-field rows are published for
the 18 mathematics subfields above the tracker's volume gate (a median of at least
50 papers a month); the other 12 subfields' papers still count in every `math` row,
and their per-paper rows are in the row-level tables. The `math` aggregate is
computed over member papers, never summed from field rows.

## Populations

| `population` | Meaning                                                        |
| ------------ | -------------------------------------------------------------- |
| `all`        | every paper in the cell, the default and what the charts show   |
| `panel`      | only papers with an author in the fixed panel of the paper's own field |

A `panel` row never replaces the `all` row for the same cell; both are published.
Anything reading the file must filter on `population`, or it will double-count.
The panel definition is in [`methodology.md`](methodology.md); the per-author flag is
in the `author_fields` table.

Read panel comparisons **inside 2023 onward only**, never against the 2019–2022
definition window (members were selected for producing then), and baseline on 2024
rather than 2023 (regression to the mean predicts a dip right after selection, and
the data shows one). Never sum panel rows across fields; read the `math` row.

## Partial periods

The current month is always incomplete, and announcement lag means the previous one
may be. `is_partial` marks affected rows. Never silently drop them; a missing trailing
point reads as a decline.

## Provenance

`provenance` records the stage and input version, e.g. `metadata`,
`metadata:tenure:full`, `fulltext:ai_tools.v2:tax3`. Term lists and taxonomies
drift, so a published series is scored end to end by a single version, and a version
bump re-scores the whole history rather than appending. The `tax3` suffix marks the
current use-case taxonomy; do not chart it against earlier taxonomies.

## Metric registry

| `metric`              | Kind  | Population | `category` values |
| --------------------- | ----- | ---------- | ----------------- |
| `papers_total`        | count | all, panel | — |
| `authors_band`        | rate  | all, panel | `1`, `2`, `3`, `4plus`, **partitions its denominator** |
| `authors_per_paper`   | mean  | all, panel | — |
| `ai_ack_rate`         | rate  | all, panel | — |
| `ai_no_use_rate`      | rate  | all, panel | — |
| `ai_ack_purpose`      | rate  | all, panel | `generated`, `formalized`, `research`, `lit_review`, `writing`, `other`; from 2023-01; **multi-label** |
| `ai_ack_vendor`       | rate  | all, panel | `openai`, `anthropic`, `google`, `microsoft`, `deepseek`, `other`, `unnamed`; from 2023-01; **multi-label** |
| `ai_ack_authors_band` | rate  | all, panel | `1`, `2`, `3`, `4plus`, **one denominator each** |
| `ai_ack_novelty`      | rate  | all, panel | `fresh`, `established`, **one denominator each**; from 2023-01 |
| `fresh_author_rate`   | rate  | all        | — ; from 2023-01 |
| `author_tenure`       | rate  | all        | `debut`, `years_0_5`, `years_5_10`, `years_10_plus`, **partitions its denominator**, denominated in authors |
| `panel_adopted_rate`  | rate  | panel      | — ; cumulative, from 2023-01 |
| `total_adopted_rate`  | rate  | all        | — ; cumulative, from 2023-01 |

Not included, though present on the tracker: `lean_proof_rate` (papers claiming a
machine-checked Lean formalization, from a separate triage tier) and
`pages_per_paper` (from the metadata comments field). Neither can be rebuilt from
this repository's tables.

### Reading rules by metric

- **`authors_band`** partitions: every band is written for every cell, zeros
  included, and the bands sum to the shared denominator. `authors_per_paper` sits
  beside it because bands cannot reconstruct a mean (`4plus` has no upper bound).
  Plot levels, not shares, by default: a solo-paper surge reads as nothing in a
  share chart.
- **`ai_ack_purpose`** is multi-label: a paper acknowledging AI for writing and for
  code contributes to two rows, so purpose rows sum to more than `ai_ack_rate`. Do
  not present them as a partition. `generated` counts only papers whose
  Generated-the-math tags carry explicit attribution. `ai_ack_vendor` is multi-label
  for the same reason; `unnamed` is a paper that names no vendor at all.
- **`ai_no_use_rate`** counts papers that explicitly say they did not use AI. It is
  a deliberate speech act, and its spread is evidence that disclosure norms are
  formalising.
- **`ai_ack_authors_band` and `ai_ack_novelty`** each carry their own denominator:
  category `1` reads "of examined solo papers, this many acknowledged AI". Never sum
  their rates. Their denominators do partition the examined set, which is what lets a
  front end rebuild levels. The novelty cut must not be charted as a fresh-versus-
  established comparison: the apparent gap is team size, not novelty.
- **`fresh_author_rate`** is the share of papers with an author who has no paper in
  the preceding five years. A fixed lookback, not first-ever: first-ever is censored
  by any harvest floor and never stops decaying. Valid from five years after the
  floor.
- **`author_tenure`** buckets each month's distinct posting authors by months since
  their first mathematics paper on arXiv (`debut` this month, `years_0_5` 1–60,
  `years_5_10` 61–120, `years_10_plus` 121+). It uses first-ever, safe here because
  the metadata history reaches back to 1989. Tenure is time on arXiv, not career age;
  pre-arXiv careers are invisible, which only ever moves authors into younger
  buckets. Population `all` only: the panel's tenure mix would be an artefact of its
  own definition. Rebuild it from `authors.first_paper_month` and `author_papers`.
- **`panel_adopted_rate` and `total_adopted_rate`** are cumulative: the share of
  panel members (or of all authors active since 2023) who have appeared on at least
  one disclosing paper by that month. A stock, not a flow; do not sum across months.

## Author identity

All author-level rows use the same normalised full-name key as the `authors` table
(`provenance` carries `:full`). The key over-splits one person written two ways and
cannot separate two people who share a name; see [`schema.md`](schema.md) and the
`author_ids` crosswalk for the consequences.
