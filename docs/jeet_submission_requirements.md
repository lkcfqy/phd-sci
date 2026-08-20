# JEET submission requirements and local implementation

Checked: 2026-08-21

Authoritative source: <https://link.springer.com/journal/42835/submission-guidelines>

## Current journal requirements used for this package

- Review is double blind. The manuscript and associated review files must be
  anonymized; author names, affiliations, contact details, acknowledgments, funding,
  and identity-revealing declarations belong on a separate title page.
- The title page must contain the article title, all authors and affiliations,
  corresponding-author e-mail, and available ORCIDs.
- An editable Word source is required. The guidance specifies plain 10-point Times
  Roman text, automatic page numbering, decimal headings with no more than three
  displayed levels, numeric square-bracket citations, and numbered references with DOI
  links when available.
- The abstract must contain 150--250 words and the manuscript must have 4--6 keywords.
- Figures should be cited in order and placed in the manuscript; separate source files
  should be named `Fig1`, `Fig2`, and so on. Figure captions use `Fig. N` and lettering
  should remain legible at publication size. Accessibility text and non-color-only
  distinctions are required.
- A data-availability statement and relevant Statements and Declarations, including
  competing interests, are required.
- Text supplementary material is submitted as PDF and cited in the article as an
  Online Resource.
- The subscription route is not cost-free. The current guidance lists page charges of
  US$50 per page within six pages, US$60 per page for pages 7--12, and US$80 per page
  over 13 pages. The publisher determines production length, so the corresponding
  author must reconfirm the applicable charge before submission.

## Package mapping

| Requirement | Local artifact |
|---|---|
| Anonymous editable article | `submission/jeet/Manuscript_Anonymous.docx` |
| Review PDF | `submission/jeet/Manuscript_Anonymous.pdf` |
| Separate identity/funding file | `submission/jeet/Title_Page_AUTHOR_INPUT_REQUIRED.docx` |
| Editor letter | `submission/jeet/Cover_Letter_AUTHOR_INPUT_REQUIRED.docx` |
| Online Resource 1 | `submission/jeet/ESM_1_Supplementary_Material.pdf` |
| Online Resource 2 | `submission/jeet/ESM_2_Reproducibility_Code.zip` |
| Separate figure sources | `submission/jeet/figures/Fig1.*` through `Fig11.*` |
| Audit and human gates | `submission/jeet/QA_Report.md` and `Submission_Checklist.md` |

## Do not submit yet if any of these remain unresolved

- any `REQUIRED` or bracketed placeholder remains in a file intended for upload;
- author order, CRediT roles, funding, acknowledgments, or corresponding-author status
  has not been approved by every author;
- the completed title page has accidentally been merged into the anonymous manuscript;
- the final files have not been opened and paged through in the exact Word/PDF viewers
  used for submission;
- the live journal page has not been rechecked for indexing, fees, declarations, and
  upload-field changes.
