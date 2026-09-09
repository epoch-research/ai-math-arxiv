# Data Schema

Column-level reference for the seven row-level tables in `data/`, as returned by
`arxiv_math_ai_data.get_all_tables()`. The eighth table, the monthly chart series,
has its own reference in [`monthly-series.md`](monthly-series.md).

## Conventions

- **Months** are `YYYY-MM` and always mean the paper's **first-version (v1)
  submission month**, never the month it was announced or last revised.
- **Fields** are arXiv primary categories (`math.CO`), see the table at the end.
  A paper cross-listed to several categories counts once, under its primary. The
  value `all` in `examined` is the aggregate over every mathematics-primary paper,
  computed over the papers themselves and never summed from field rows.
- **arXiv ids** are strings (`2606.00001`, `math/0601001`); load them as strings or
  the trailing zeros are lost. `url` columns point to `https://arxiv.org/abs/<id>`.
- **Author keys** (`author`) are normalised name strings: lower-case, TeX escapes
  resolved, accents folded, punctuation removed, every name token kept (`"j p serre"`,
  `"terence tao"`). They are the join key across the four author tables.
- **Empty strings** mean "none": an empty `orcid` is an OpenAlex author without one,
  an empty `bucket` is a tag that does not count toward any published bucket.
- **Booleans** are written `True` / `False`.
- Multi-valued text columns join their values with `; `.

## `disclosures` — `data/math_disclosures.csv`

One row per (paper, use tag). A paper with three tags appears three times. Every
paper here is counted in the published disclosure rate, and every paper counted in
the rate is here.

| Column | Type | Notes |
|--------|------|-------|
| `arxiv_id` | str | |
| `url` | str | `https://arxiv.org/abs/<arxiv_id>` |
| `month` | str | v1 submission month |
| `field` | str | primary category |
| `tag` | str | fine use tag, one of the 19 use tags in the vocabulary below |
| `bucket` | str | the published use-case bucket the tag rolls into: `generated`, `formalized`, `research`, `lit_review`, `writing`, `other`; empty for a `purpose_unstated` tag on a paper that has other buckets |
| `attribution` | str | for the three Generated-the-math tags only: `explicit` (a specific result and a tool act are both named) or `vague`; empty otherwise |
| `verifier` | str | the second model's verdict on this tag: `supported`, `borderline`, or `unchecked` (verifier request errored) |
| `quote` | str | verbatim text from the paper supporting the tag, whitespace collapsed to single spaces |
| `tools_named` | str | every AI tool or proof assistant the paper credits, verbatim, `; `-joined; paper-level, repeated on each of the paper's rows |
| `vendors` | str | vendors derived from `tools_named`: `openai`, `anthropic`, `google`, `microsoft`, `deepseek`, `other`, `unnamed`; `; `-joined; paper-level |
| `confidence` | str | the tagger's paper-level confidence: `high`, `medium`, `low` |

**Bucket rules.** The three Generated-the-math tags (`main_results_generated`,
`specific_result_generated`, `conjecture_generated`) roll into `generated` when the
paper's `attribution` is `explicit` and into `research` otherwise. `purpose_unstated`
is a residual: it rolls into `other` only when it is the paper's sole use tag. Buckets
are multi-label; a paper's buckets are the set of non-empty `bucket` values on its
rows, and they do not partition anything.

## `examined` — `data/math_examined.csv`

One row per (month, field), plus one `all` row per month. The published disclosure
rate for a cell is `papers_disclosing / papers_examined`.

| Column | Type | Notes |
|--------|------|-------|
| `month` | str | v1 submission month |
| `field` | str | primary category, or `all` |
| `papers_listed` | int | mathematics-primary papers submitted in the cell |
| `papers_examined` | int | of those, papers whose TeX source was retrieved and parsed — the denominator |
| `papers_disclosing` | int | examined papers counted as disclosing AI use (= distinct `arxiv_id` in `disclosures` for the cell) |
| `papers_denying` | int | examined papers that explicitly state no AI was used, and disclose no use |
| `is_partial` | bool | the month was still open, or within announcement lag, when the snapshot was taken |

`papers_listed` exceeds `papers_examined` where source was PDF-only or failed to
parse (about 2% of papers). Rows exist for every cell with at least one examined
paper; a missing cell means no data, never a measured zero.

## `papers` — `data/math_papers.csv.gz`

One row per mathematics-primary paper listed from January 2023 to the last examined
month, with what the pipeline did with it. This is the table to consult for "was this paper checked at
all, and what came of it".

| Column | Type | Notes |
|--------|------|-------|
| `arxiv_id` | str | |
| `month` | str | v1 submission month |
| `field` | str | primary category |
| `examined` | bool | TeX source was retrieved and parsed; the paper is in the denominator |
| `outcome` | str | one of the values below |

| `outcome` | Meaning |
|-----------|---------|
| `not_examined` | no parseable TeX source (PDF-only or extraction failed); not in any denominator |
| `no_hit` | examined; no AI-related keyword matched, so the paper was never read by the model |
| `no_disclosure` | read; no disclosure of AI use in the rendered text (a name collision, a citation, or a disclosure present only in TeX comments) |
| `subject_matter` | the paper is about AI; excluded from every disclosure series even if its authors also used AI |
| `denial` | the authors explicitly state that no AI was used, and disclose no use |
| `disclosure` | counted as disclosing AI use; its tags and quotes are in `disclosures` |
| `unresolved` | keyword hit, but no verdict: the classification request errored or the source could not be re-extracted for the model; in the denominator, not the numerator |

Per (month, field), `examined == True` counts to `examined.papers_examined`,
`disclosure` to `papers_disclosing`, and `denial` to `papers_denying`; every row
counts to `papers_listed`.

## `authors` — `data/math_authors.csv.gz`

One row per author key. Covers every author on every paper in arXiv's mathematics
set (any paper with a `math.*` category, whether or not it is the primary), from the
first mathematics submissions in 1989.

| Column | Type | Notes |
|--------|------|-------|
| `author` | str | the author key |
| `name` | str | the most frequent spelling of the name on arXiv bylines, TeX resolved, accents kept |
| `first_paper_id` | str | earliest paper in the mathematics set (earliest month; ties broken by id) |
| `first_paper_month` | str | its v1 month — the author's first appearance in arXiv mathematics, not first paper anywhere |
| `first_paper_url` | str | |
| `last_paper_month` | str | v1 month of the latest paper |
| `n_papers` | int | distinct papers in the mathematics set |
| `n_papers_math_primary` | int | of those, papers whose primary category is a `math.*` field |

Bylines that cannot be split into people — "et al." lists and named collaborations —
are dropped rather than partially credited, so a handful of papers have no author
rows.

## `author_fields` — `data/math_author_fields.csv.gz`

One row per (author, math field) with at least one math-primary paper.

| Column | Type | Notes |
|--------|------|-------|
| `author` | str | |
| `field` | str | a `math.*` primary category |
| `n_papers_in_field` | int | math-primary papers with this primary category |
| `n_papers_2019_2022` | int | of those, submitted 2019-01 to 2022-12 — the panel's definition window |
| `panel` | bool | member of this field's fixed author panel: `n_papers_2019_2022 >= 3`, at least 5 core-journal papers in OpenAlex, and at least one mathematics paper (any field) from 2023-01 on |

Panels are per field and **must not be summed across fields**: an author active in
two fields can be in both panels. Roughly 8% of members across the published fields
are in more than one panel.

## `author_papers` — `data/math_author_papers.csv.gz`

One row per (author, paper).

| Column | Type | Notes |
|--------|------|-------|
| `author` | str | |
| `arxiv_id` | str | |
| `month` | str | v1 submission month |
| `field` | str | the paper's primary category (may be outside `math.*` for cross-lists) |
| `is_math_primary` | bool | |

## `author_ids` — `data/math_author_ids.csv.gz`

The crosswalk from author keys to OpenAlex author ids and ORCIDs. One row per
(author key, OpenAlex author id, ORCID) that co-occur on at least one paper.

| Column | Type | Notes |
|--------|------|-------|
| `author` | str | |
| `openalex_author_id` | str | `https://openalex.org/A...` |
| `orcid` | str | `https://orcid.org/...` as recorded by OpenAlex; empty when none |
| `n_shared_papers` | int | papers on which OpenAlex's authorship and our byline resolve to the same name |

A link is made only within a paper both sources describe: OpenAlex's authorship on
that paper must normalise to a name on our byline for the same paper. Names are
never matched globally, so a common name cannot be linked to a stranger's record.
Within an author, rows are ordered best-supported first. One key mapping to several
OpenAlex ids (about 17% of linked keys) usually means OpenAlex split the person;
one OpenAlex id spanning several keys (about 5% of ids) usually means we did.
OpenAlex works were pulled for papers from 2018 onward, so an author whose last
mathematics paper predates 2018 has no row.

## The use-tag vocabulary

| Tag | The model tags this when... | Bucket |
|-----|------------------------------|--------|
| `main_results_generated` | AI produced essentially all of the paper's mathematics | `generated` if `attribution` is explicit, else `research` |
| `specific_result_generated` | a specific proof, construction, formula, bound, or counterexample in the paper is attributed to AI | same |
| `conjecture_generated` | AI produced the conjecture, candidate object, or statement; the humans proved it | same |
| `formalization_assist` | AI assisted a machine formalization (Lean, Isabelle, Coq) of the paper's own results | `formalized` |
| `proof_ideas` | brainstorming, strategy, suggested directions or lemma attempts not themselves results in the paper | `research` |
| `code_computation` | writing code, computation, simulation | `research` |
| `notes_organization` | summarizing or organizing the authors' own notes or logs | `research` |
| `ai_as_instrument` | the study's own methodology runs on AI | `research` |
| `benchmarked_own_problem` | the authors tested an AI on the paper's own problem and report how it did | `research` |
| `math_checking` | verifying proofs, constants, or derivations; finding mathematical errors | `research` |
| `literature_search` | finding references, related work, or what a concept is called | `lit_review` |
| `writing_polish` | style, grammar, rephrasing, LaTeX and formatting help, proofreading | `writing` |
| `draft_text_generated` | AI wrote substantial portions of the manuscript's prose | `writing` |
| `translation` | translating the manuscript or sources | `writing` |
| `draft_feedback` | AI feedback or review on the draft | `writing` |
| `figures_media` | generating figures, diagrams, artwork | `other` |
| `ai_generated_content_embedded` | AI-produced text printed as content (an epigraph, a quoted answer) | `other` |
| `purpose_unstated` | a genuine disclosure that states no purpose | `other`, as a residual only |
| `other` | a stated purpose that fits no tag above | `other` |

Four further tags exist in the pipeline but never appear here: `subject_matter`
(the paper is about AI; such papers are excluded from every disclosure table),
`no_use_declared` (counted in `papers_denying`), and the two false-positive tags
`name_collision` and `passing_mention`.

## Fields

The 30 mathematics primary categories present in the data. `math.IT` and `math.MP`
are aliases of `cs.IT` and `math-ph` on arXiv and do not occur as primaries here.

| Code | Name | Code | Name |
|------|------|------|------|
| `math.AC` | Commutative Algebra | `math.GT` | Geometric Topology |
| `math.AG` | Algebraic Geometry | `math.HO` | History and Overview |
| `math.AP` | Analysis of PDEs | `math.KT` | K-Theory and Homology |
| `math.AT` | Algebraic Topology | `math.LO` | Logic |
| `math.CA` | Classical Analysis and ODEs | `math.MG` | Metric Geometry |
| `math.CO` | Combinatorics | `math.NA` | Numerical Analysis |
| `math.CT` | Category Theory | `math.NT` | Number Theory |
| `math.CV` | Complex Variables | `math.OA` | Operator Algebras |
| `math.DG` | Differential Geometry | `math.OC` | Optimization and Control |
| `math.DS` | Dynamical Systems | `math.PR` | Probability |
| `math.FA` | Functional Analysis | `math.QA` | Quantum Algebra |
| `math.GM` | General Mathematics | `math.RA` | Rings and Algebras |
| `math.GN` | General Topology | `math.RT` | Representation Theory |
| `math.GR` | Group Theory | `math.SG` | Symplectic Geometry |
| | | `math.SP` | Spectral Theory |
| | | `math.ST` | Statistics Theory |

## Coverage

The disclosure, examined and papers tables run from 2023-01 to the latest month in
`data/manifest.json`. The pipeline measures from 2018-01, but 2018–2022 holds four
disclosing papers in five years and was read as excerpts rather than full text, so
the public dataset begins where the full-text tier does. The author tables cover
arXiv's mathematics set from its first submissions (1989) to the snapshot date.
