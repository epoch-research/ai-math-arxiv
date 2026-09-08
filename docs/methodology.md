# Methodology

The full write-up is published with the tracker at <https://epoch.ai/data/arxiv>.
This page summarises the decisions that shape the tables in this repository.

## Summary of approach

arXiv is treated as a public behavioural trace of mathematical research practice.
Every mathematics paper's TeX source is scanned for AI-related terms; papers with a
hit are read by a language model that tags each disclosed use of AI with a verbatim
quote; a second model tries to refute every tag; the surviving tags are rolled up to
published use-case buckets. Separately, arXiv bylines are resolved to author keys,
from which each field's fixed author panel and the author-level series are built.

## Papers → AI-use disclosures

### 1. Corpus

Metadata for every paper in arXiv's mathematics set is harvested through OAI-PMH,
using the `arXivRaw` format because it carries the version history. A paper is dated
by its **first-version submission month**, never by announcement or revision date.
A paper's field is its **primary** category; cross-lists are not double-counted.

TeX source is pulled from arXiv's bulk source archives for every mathematics-primary
paper from 2018-01 on. Source that is PDF-only or fails to parse (about 2% of papers)
is not examined, and those papers are excluded from the denominator rather than
counted as non-disclosing. The `examined` table carries both counts.

### 2. Keyword scan

Rendered text and TeX comments are scanned separately with a fixed, versioned list of
regular expressions (`ai_tools.v2`): tool names (ChatGPT, GPT-4/5, Claude, Gemini,
DeepSeek, Copilot, Lean-adjacent AI provers...), generic phrasings ("large language
model", "generative AI", "use of AI", bare `AI`), and vendor names. The list is tuned
for recall; most hits are false positives (a person named Claude, a citation, a
paper about machine learning) and the classifier, not the regex, removes them.

Papers with no hit are never read. **Every rate is therefore a floor**: a paper that
discloses AI use in words the list does not match is invisible.

### 3. Classification

One request per hit paper to Claude Fable 5 (Batch API, strict JSON schema).

- **2023 onward — full text.** The whole paper, comments stripped, followed by the
  comment stream. Papers over about 110,000 characters were truncated in the middle
  (see limitations).
- **2018 to 2022 — excerpts.** Every matched passage plus every acknowledgment-like
  section (acknowledgments, declarations, funding, author contributions, competing
  interests, any heading naming AI). Disclosures in these years number in single
  digits per year, and an earlier full re-read of a 400-paper sample flipped none of
  the excerpt-tier verdicts.

The model returns a set of **tags** from a closed 23-tag vocabulary (19 use tags, 4
non-use tags: about-AI, explicit non-use, name collision, passing mention), each with
a **verbatim quote** and the stream it came from. No quote, no tag. It also returns
the tools named, an `attribution` field (explicit / vague) for the Generated-the-math
tags, and a paper-level confidence. It is told to judge only what the text states,
never to infer use from style, and to mark tags on named fuzzy boundaries as
borderline rather than guess.

### 4. Quality control

1. **Quote verification.** Every quote is checked as a substring of the text shown
   to the model. Tags whose quote is not found are dropped.
2. **Adversarial pair verification** by Claude Opus 5 on every tag: shown the
   definition, the quote, and the surrounding text, it tries to refute the tag and
   answers `supported`, `unsupported`, or `borderline`. Unsupported tags are dropped
   and logged.
3. **Blind second read** of every paper carrying a Generated-the-math or
   formalization tag, by Opus under the identical prompt; disagreements go to a human
   queue.
4. **Triage.** Supported tags are kept; borderline tags are kept and queued for
   human adjudication where the bucket is at stake. **That adjudication is pending**;
   the `verifier` column lets a reader exclude borderline tags if they prefer.

### 5. From tags to the published tables

- A paper **counts as disclosing** if, after QC, it has at least one use tag whose
  quote is from the rendered text. Comment-only disclosures are excluded from the
  per-paper tables (they are an aggregate sub-series on the tracker).
- Papers with a `subject_matter` tag are **excluded** from every disclosure table,
  even when their authors also used AI: the paper is about AI, and counting it as
  adoption double-reads the topic as the toolbox.
- **Denials** count in `papers_denying` only when no use is disclosed; a scoped
  denial beside a disclosure is a disclosure.
- Use tags roll up to **six buckets**: Generated the math (explicit attribution
  only), Formalized the result, Research assistance (including vague-attribution
  generation and math checking), Literature search, Writing, Other / unspecified.
  Buckets are multi-label and are not a partition.
- **Vendors** are derived from the tools named by a regular-expression table; proof
  assistants, language-checking aids, and access routes such as Poe or OpenRouter
  are not vendors.

### Known limitations

- **It is a floor** (section 2).
- **Recent months rise after publication.** Disclosure statements are commonly added
  at journal revision. Each refresh re-reads revised papers; a month's count is "as
  of the snapshot".
- **Truncation of long papers hid some disclosures.** About 36% of full-text papers
  were truncated in the middle on the assumption that acknowledgments sit at the end
  of the source. Often they do not (files concatenate in filename order; appendices
  follow acknowledgments). A hand review of the affected papers found on the order
  of 2–3% additional disclosing papers in 2026 that the model never saw. A re-read of
  the affected papers with the matched passages always included is planned; until
  then this is a further reason the rate is a floor.
- **Borderline tags are unadjudicated** (section 4).
- **Model judgement is model judgement.** Two models cross-check each other and every
  tag carries a receipt, but no human has read most of these papers. In an earlier
  validation round the headline disclosure count moved by 0.5% under a model swap,
  while individual purpose labels churned around 25%; the full-text read, the quote
  requirement, and the QC stack were built to reduce that churn.

## Authors

### Identity

Author identity comes from **arXiv bylines**, not OpenAlex. arXiv gives a free-text
author string and no identifiers, so "the same author" is a rule: the byline is split
into names, TeX escapes are resolved, accents folded, punctuation removed, and every
token kept, lower-case. That key over-splits a person written two ways (about 5.5%
over-count of distinct authors) and cannot separate two people who share a full name.
The alternative "initial + surname" key merges hundreds of distinct people into one
and is not used here.

Bylines that cannot be split into people ("et al.", a named collaboration) are dropped
rather than partially credited.

### First paper

`first_paper_month` is the author's first appearance in **arXiv's mathematics set**,
which the metadata harvest covers back to arXiv's first mathematics submissions in
1989. Cross-listed papers count toward first appearance. Careers before arXiv, or
outside mathematics on arXiv, are invisible; this only ever makes an author look
newer than they are.

### The panel

Each field has a fixed author panel, chosen on pre-ChatGPT data and tracked forward,
so that a change in output can be read as a change in what the same people did. An
author is in field F's panel if all three hold:

1. at least **3 distinct papers with primary category F during 2019–2022**;
2. at least **5 papers in core journals** according to OpenAlex (authors who cannot be
   identified in OpenAlex at all are excluded, not treated as zero);
3. at least **one further mathematics paper, in any field, from 2023-01 on**.

The window predates ChatGPT so the productivity bar cannot be contaminated by the
thing being measured; the journal bar answers the objection that posting preprints is
not the same as the literature accepting one's work; the still-active bar keeps the
panel to the established core that is still present. Panels are per field and near-
but not perfectly disjoint: never sum them across fields.

### OpenAlex and ORCID crosswalk

OpenAlex works were fetched for the 2018-onward corpus, matched to arXiv papers by
DOI. For each paper both sources describe, each OpenAlex authorship's name is
normalised with the same rule as our keys and matched against our byline for that
paper. A match links (author key, OpenAlex author id, ORCID) and the number of such
papers is the link's support. Matching only within a shared paper is what keeps a
common name from being linked to a stranger's record. OpenAlex is used for identity
only; it is never a denominator, because its coverage of the corpus varies too much
by month to count against.

## Refresh cadence

arXiv publishes the previous month's source archives around the 5th. The pipeline
then harvests new metadata, pulls new and rebuilt source, re-scans, classifies only
new and changed papers (content fingerprints make this incremental), and republishes.
The files in `data/` are replaced wholesale; `manifest.json` records the snapshot.
