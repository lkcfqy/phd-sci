# JEET submission-package QA report

Date: 2026-08-21

This is an internal handoff record. Do not upload it as a manuscript file.

## Completed checks

- The anonymous manuscript source has a 247-word abstract, six keywords, 33 cited
  bibliography entries, three consecutively cited tables, and eleven consecutively
  cited figures.
- `Manuscript_Anonymous.docx` contains three Word tables, eleven embedded figures with
  alternative descriptions, Times New Roman styles, an automatic page-number field,
  anonymous core properties, and no known local username, author placeholder, or
  affiliation token.
- The separate title page and cover letter deliberately retain conspicuous
  `AUTHOR_INPUT_REQUIRED` filenames, document metadata, and bracketed fields.
- `Manuscript_Anonymous.pdf` has 16 portrait pages; all 16 pages were rendered at
  144 dpi and visually inspected for clipping, overlap, broken figure/caption pairs,
  missing-glyph boxes, table overflow, and unintended blank pages.
- `ESM_1_Supplementary_Material.pdf` has six landscape pages; all six pages were
  rendered at 144 dpi and visually inspected for the same defects. Its 14 tables fit
  within their page frames, and multiline limitation bullets remain intact.
- Both review PDFs report `Anonymous` as the PDF author and passed page-size,
  extractable-text, near-blank-page, and identity-token audits.
- The reproducibility ZIP has an installable project shape, excludes raw/processed
  datasets, Git history, local paths, submission-build utilities, and submission-only
  tests, and contains an internal SHA-256 manifest covering every archived file except
  the manifest itself.
- The final binary hashes and PDF page audits are recorded in `build_metadata.json`.

## Renderer boundary

The workstation did not contain Microsoft Word or LibreOffice, so a native Word-engine
render of the three DOCX files was not available. The manuscript and supplement review
PDFs were generated directly from the same frozen Markdown, BibTeX, figure, caption,
and citation-order sources and received full page-by-page visual inspection. The DOCX
files received OOXML structure, metadata, content, figure-count, table-count, style,
page-field, and anonymity checks instead.

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
