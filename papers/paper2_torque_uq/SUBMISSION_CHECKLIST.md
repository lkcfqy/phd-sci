# Paper 2 submission checklist

Updated: 2026-08-21

## Technical package: passed

- [x] Evidence-locked 5,158-word manuscript with an abstract below 250 words.
- [x] Public-data audit: 23,250 designs, six source files hashed, no null values, duplicate
  rows, or exact cross-table parameter overlap.
- [x] Frozen fit/calibration/test roles and five deterministic split seeds.
- [x] Four surrogate comparators, two nominal coverage levels, three evaluation
  distributions, support warning, distance-quintile audit, and weighted-conformal
  diagnostic.
- [x] Negative results retained: 76.13%/78.31% sparse-tail coverage and 0/5,000 finite
  Gaussian weighted bands.
- [x] Five publication figures visually inspected in PNG and PDF form.
- [x] Anonymous DOCX structural audit: 149 paragraphs, 5 tables, 5 inline figures, and 10
  cited references.
- [x] Anonymous 15-page PDF visually inspected page by page with no clipping, overlap,
  missing glyph, incorrect list numbering, or detached caption.
- [x] Anonymous DOCX rendered with Microsoft Word and all 15 native-render pages inspected
  with no clipping, overlap, broken table, missing figure, or detached caption.
- [x] Mechanical claim validator passed against 42,900 primary per-design rows and the
  disjoint weighted diagnostic.
- [x] Supplementary material generated from frozen result tables and checked for drift.
- [x] Four-page landscape supplementary PDF generated, structurally audited, and visually
  inspected page by page; all 11 tables fit without clipping or overlap.
- [x] Reproducibility bundle contains 80+ source/result/figure/test files, checks every member
  hash, and excludes raw public data.
- [x] Full repository checks: Ruff passed and all 271 pytest tests passed.

## Author and target-journal fields: complete immediately before submission

- [ ] Insert final author names, affiliations, corresponding-author address, and ORCID IDs.
- [ ] Confirm funding, competing-interest language, and CRediT contributions with every
  author.
- [ ] Deposit the companion code/bundle and replace the placeholder repository URL and DOI.
- [ ] Select the target journal, apply its Word/LaTeX template, reference style, word limits,
  figure-resolution rules, and required declarations.
- [ ] Re-render and inspect the journal-templated DOCX after target-journal pagination changes.
- [ ] Run the target journal's similarity, authorship, and generative-AI disclosure checks.
- [ ] Prepare journal-specific highlights, graphical abstract, cover letter, and suggested
  reviewers if requested.

These remaining items are administrative or journal-specific. They do not require changing
the frozen scientific results unless the selected journal requests a different analysis.
