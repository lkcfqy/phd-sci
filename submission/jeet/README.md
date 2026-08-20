# JEET submission package

Generated: 2026-08-21

## Upload files

1. `Manuscript_Anonymous.docx` - double-blind review manuscript with inline figures,
   tables, numeric citations, declarations, and no author identity.
2. `Title_Page_AUTHOR_INPUT_REQUIRED.docx` - replace every bracketed field, obtain all
   author approvals, then rename to `Title_Page.docx`.
3. `Cover_Letter_AUTHOR_INPUT_REQUIRED.docx` - complete and sign before upload.
4. `ESM_1_Supplementary_Material.pdf` - anonymous detailed evidence (Online Resource 1).
5. `ESM_2_Reproducibility_Code.zip` - anonymous code, tests, protocols, and selected
   derived outputs (Online Resource 2).
6. `figures/Fig1` through `Fig11` - editable/vector PDF plus 300-dpi review PNG copies.

## Internal control file

`QA_Report.md` records the completed visual and structural checks and the remaining
native-Word/human gates. Keep it with the working package, but do not upload it as a
manuscript file.

## Remaining human-only gates

- Confirm author names, order, affiliations, ORCIDs, corresponding author, CRediT roles,
  acknowledgments, and funding.
- Every author must inspect and approve the full manuscript, declarations, AI-assistance
  disclosure, supplementary material, and cover letter.
- Confirm the work is not under consideration elsewhere and obtain institutional
  permission to submit.
- Recheck the live journal site on submission day. JEET currently uses double-blind
  review and requests a separate title page.

## Rebuild

Run `scripts/build_jeet_submission.py` and then `scripts/build_jeet_pdfs.py`. The first
command rebuilds the editable Word sources, figures, and anonymous code bundle; the
second creates and audits the two review PDFs. Per-artifact SHA-256 values and PDF page
audits are in `build_metadata.json`.
