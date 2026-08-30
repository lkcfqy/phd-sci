# Full-project migration notes

Prepared: 2026-08-23

## Archive scope

The full migration archive contains the scientifically relevant project state:

- Git metadata and the complete current worktree, including tracked and untracked research files;
- raw and processed datasets under `data/`;
- frozen configurations, source modules, scripts, tests, references, and documentation;
- all result tables, figures, manuscripts, supplementary materials, submission packages, and
  reproducibility bundles for Papers 1--4; and
- project metadata such as `pyproject.toml`, `.gitignore`, and `.gitattributes`.

The following regenerable or machine-local directories are deliberately excluded:

- `.venv/`: a Windows virtual environment is not portable across machines or Python installs;
- `.pytest_cache/`, `.ruff_cache/`, and all `__pycache__/` directories;
- `tmp/`: partial downloads, renderer outputs, page rasterizations, and other temporary QA files.

No source dataset, processed dataset, scientific result, manuscript, submission artifact, or Git
history is excluded.

## Restore

Extract the archive into the destination directory. It contains one top-level directory named
`phd sci`.

```powershell
tar -xf phd_sci_full_2026-08-23.tar.zst -C C:\destination
Set-Location 'C:\destination\phd sci'
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,publication]"
ruff check .
pytest -q
```

The frozen workstation verification before packaging was Ruff passed and 271/271 pytest tests
passed. Microsoft Word and the bundled publication runtime were used for final document QA; those
applications are not embedded in the archive.

## Integrity check

Keep the archive and its `.sha256` sidecar together. Before extraction, compute:

```powershell
(Get-FileHash .\phd_sci_full_2026-08-23.tar.zst -Algorithm SHA256).Hash.ToLower()
```

The value must match the sidecar exactly. A separate inventory sidecar records archive size, member
count, included root, exclusions, and the final hash.
