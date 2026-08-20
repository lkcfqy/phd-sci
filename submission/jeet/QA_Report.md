# JEET submission-package QA report

Date: 2026-08-21

This is an internal handoff record. Do not upload it as a manuscript file.

## Completed checks

- The anonymous manuscript source has a 247-word abstract, six keywords, 34 cited
  bibliography entries, three consecutively cited tables, and eleven consecutively
  cited figures.
- The main title is a 12-word, dataset-and-task-specific statement. The abstract defines
  AUROC at first use, and a curated technical check verifies first-use expansions for
  PMSM, KAIST, DANN, MMD, CORAL, SVM, SPD, CRC, SHA-256, TDMS, RMS, CI, FAR, H1, MD5,
  AUPRC, CC BY, and LLM.
- `Manuscript_Anonymous.docx` contains three Word tables, eleven embedded figures with
  alternative descriptions, Times New Roman styles, an automatic page-number field,
  anonymous core properties, and no known local username, author placeholder, or
  affiliation token.
- The separate title page and cover letter deliberately retain conspicuous
  `AUTHOR_INPUT_REQUIRED` filenames, document metadata, and bracketed fields.
- `Portal_Clarification_Email_Draft.md` is generated as an internal, explicitly unsent
  routing inquiry; it asks the journal to confirm the active portal, double-blind file
  arrangement, and charge treatment without attaching the manuscript.
- The separate title page follows the KIEE April 2025 declaration inventory: funding,
  author contributions, competing interests, ethics approval, consent to participate,
  consent for publication, data/materials/code availability, and generative-AI use are
  grouped under `Statements and declarations`.
- `Manuscript_Anonymous.pdf` has 18 portrait pages and
  `ESM_1_Supplementary_Material.pdf` has eight landscape pages. All 26 final pages were
  rendered at 180 dpi and visually inspected for clipping, overlap, broken
  figure/caption pairs, missing-glyph boxes, table overflow, and unintended blank pages.
  After the engineering-scope revision, manuscript pages 1, 5--7, and 15 and
  supplementary page 1 were re-inspected; the other 20 pages matched the preceding
  fully inspected render byte for byte. The supplement's 17 tables all fit within
  their page frames.
- All figure-wide titles, subtitles, and caption-like footer prose were removed from the
  uploaded artwork. The corresponding denominators, interval definitions, H1 limits,
  dependence warnings, and single-motor caveats are carried by synchronized manuscript
  captions. Vector PDFs are the upload-quality figure sources; 300 dpi PNGs are retained
  as review/Word copies. Two complete figure regenerations produced identical PDF
  SHA-256 values.
- A lower-grain evidence audit independently reconstructed every headline denominator
  and performance result used in the abstract, results, and conclusion. It also exposed
  and corrected the fixed fault-turn/phase confounding, unequal load support in pooled
  external AUROC, and one 0.01 percentage-point interval-rounding discrepancy.
- A dated reference audit resolved all 34 cited records through DOI registries or the
  publisher page and found no normalized title, first-author, or available-year mismatch.
- The external dataset's linked primary machine paper was inspected directly. Its
  Table I supports the 30.16 kW, 200 V DC-link, 107 A continuous-current, ten-pole-pair,
  and 8000 rpm parameters now reported in Section 5.2. The Discussion explicitly states
  that the analyses were offline and that no latency, memory, or embedded-feasibility
  claim was tested. A three-perspective internal red-team review records the remaining
  scientific and editorial risks in `docs/mock_peer_review_2026-08-21.md`.
- S9 preserves the frozen `0/21` parser-compatibility failure separately from the
  post-reveal implicit-time repair; it does not present the 200 W sensitivity as a
  third confirmatory validation dataset.
- Both review PDFs report `Anonymous` as the PDF author and passed page-size,
  extractable-text, near-blank-page, and identity-token audits.
- The document-skill accessibility audit reported zero high-, medium-, or low-severity
  findings for the anonymous manuscript, title-page template, cover-letter template,
  and intermediate supplementary DOCX.
- The reproducibility ZIP has an installable project shape, excludes raw/processed
  datasets, Git history, task-local absolute paths, submission-build utilities, and
  submission-only tests. It includes the anonymous manuscript source, bibliography and
  reference-audit snapshot, lower-grain prediction tables needed for the independent
  manuscript-evidence check, both secondary transient-audit protocols, and the selected
  frozen/post-reveal result directories. An internal SHA-256 manifest covers every
  archived file except the manifest itself.
- Repository-wide Ruff, the supplementary drift check, the independent manuscript-
  evidence validator, and all 145 repository tests passed. The final ZIP was extracted
  into a fresh temporary directory. With its own `src` directory placed first on the
  import path (confirmed from `pmsm_sci.__file__`), the evidence validator, all 129 tests
  shipped in the bundle, and Ruff passed without reading an unbundled result or
  processed-feature file.
- The final binary hashes and PDF page audits are recorded in `build_metadata.json`.

## Renderer boundary

The workstation did not contain Microsoft Word or LibreOffice. After the final rebuild,
the canonical DOCX renderer was invoked again and stopped with the expected
missing-executable error, so a native
Word-engine render of the three final DOCX files was not available. The manuscript and
supplement review PDFs were generated directly from the same frozen Markdown, BibTeX,
figure, caption, and citation-order sources and received full page-by-page visual
inspection. The DOCX files received OOXML structure, metadata, content, figure-count,
table-count, style, page-field, anonymity, and accessibility checks instead.

After authorship fields are completed, the corresponding author must open the final
DOCX files in the exact Word version used for upload, update fields, and inspect every
page once more. That human Word check is still a submission gate.

## Human gates still open

- author names and order;
- affiliations, e-mails, and ORCIDs;
- corresponding author;
- CRediT roles;
- funding/grant wording and acknowledgments;
- all-author approval of the declarations, AI-assistance statement, and cover letter;
- final journal-site, indexing, fee, and upload-field verification.
- confirmation of the active submission route with `jeet@kiee.or.kr` while the linked
  Editorial Manager page displays its implementation-mode warning.
