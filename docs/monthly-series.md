# The monthly series: `data/arxiv_trends_monthly.csv`

The aggregate file the tracker's charts draw. Same file the website reads, minus two
metrics this repository's tables cannot reproduce (`lean_proof_rate`,
`pages_per_paper`) and minus periods before 2023-01. Everything else in it rebuilds
from `disclosures`, `examined` and `papers`, and the test suite checks that it does.

## Columns

| Column | Type | Notes |
|--------|------|-------|
| `metric` | string | snake_case metric id, see the registry below |
| `field` | string | primary arXiv category (`math.CO`), or `math` for every mathematics paper |
| `period` | string | `YYYY-MM`, the v1 submission month |
| `population` | string | `all`, or `panel` (papers with an author in the field's fixed panel; the panel's definition is in `data/manifest.json`) |
| `category` | string | sub-breakdown within a metric; empty when the metric has none |
| `numerator` | number | see below |
| `denominator` | number | never zero; the row is omitted instead |
| `is_partial` | bool | the period was still open when the row was computed |
| `provenance` | string | which pipeline stage and input version produced the row |

A row is identified by (`metric`, `field`, `period`, `population`, `category`). There
is no `value` column; `get_monthly` adds one as `numerator / denominator`.

The math-wide aggregate is `math` here and `all` in the row-level tables.
`get_monthly(field="all")` translates.

## Everything is a ratio

| Metric kind | `numerator` | `denominator` | Reading |
|-------------|-------------|---------------|---------|
| Count | papers | `1` | a count |
| Rate | papers with the property | papers we could read | a proportion |

**To roll monthly up to a quarter or a year, sum both columns and divide**, which is
correct for both kinds.

## Denominators are not interchangeable

Full-text metrics are measured over papers whose source could be read, never papers
listed. Every metric here is denominated in papers. Rows whose denominator would be
zero are omitted, so a gap means "no data", never "measured zero".

## Fields, populations, partial periods

Per-field rows are published for the mathematics subfields above the tracker's volume
gate (a median of at least 50 papers a month); the rest still count in every `math`
row. The `math` aggregate is computed over papers, never summed from field rows.

A `panel` row never replaces the `all` row for the same cell; both are published, so
anything reading the file must filter on `population` or it will double-count. Never
sum panel rows across fields. Read panel comparisons inside 2023 onward only, never
against the 2019–2022 definition window.

`is_partial` marks the current month and any month still inside announcement lag.
Never silently drop those rows: a missing trailing point reads as a decline.

## Provenance

`provenance` records the stage and input version: `metadata` for the paper counts,
`fulltext:<term list>:<taxonomy>:<readers>` for everything read from the papers. A published
series is scored end to end by a single version, and a version bump re-scores the
whole history rather than appending. Do not chart one taxonomy against another.

## Metric registry

| `metric` | Kind | Population | `category` values |
|----------|------|------------|-------------------|
| `papers_total` | count | all, panel | — |
| `ai_ack_rate` | rate | all, panel | — |
| `ai_no_use_rate` | rate | all, panel | — |
| `ai_ack_purpose` | rate | all, panel | one per published use-case bucket; **multi-label** |
| `ai_ack_vendor` | rate | all, panel | `openai`, `anthropic`, `google`, `other`, `unnamed`; **multi-label** |
| `ai_ack_vendor_group` | rate | all, panel | `<vendor>:<bucket>`, the cross of the two above; **multi-label** in both dimensions |

Every full-text metric begins 2023-01.

Which use-case buckets exist is itself a result: a bucket is published only when its
two readers agreed closely enough, so read the categories out of the file rather than
assuming a fixed list.

### Reading rules

- **Multi-label metrics do not partition.** A paper acknowledging AI for writing and
  for code contributes to two `ai_ack_purpose` rows, so the rows sum to more than
  `ai_ack_rate`. Never stack them.
